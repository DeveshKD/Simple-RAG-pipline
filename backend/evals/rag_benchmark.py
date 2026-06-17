import asyncio
import os
import sys
import pandas as pd
from datasets import Dataset
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.core.config import settings
from app.database import AsyncSessionLocal
from app.services.pgvector_service import PgVectorService
from app.services.query_processor import QueryProcessorService

from ragas import evaluate
from ragas.metrics import Faithfulness, AnswerRelevancy, ContextPrecision
from ragas.run_config import RunConfig
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage

GROQ_API_KEY = ""

async def run_benchmark(doc_id: str):
    print("Starting RAGBench Evaluation using GROQ (Llama-3)...")
    
    vector_service = PgVectorService()
    qp_service = QueryProcessorService(vector_db_service=vector_service)
    
    groq_llm = ChatGroq(
        temperature=0, 
        model_name="llama-3.3-70b-versatile", 
        api_key=GROQ_API_KEY
    )

    test_questions = [
        "What are the three main biological plausibility problems with backpropagation that this paper attempts to address?",
        "The proposed model operates on three progressively slower timescales. What are these three timescales and what is their purpose?",
        "From a biological perspective, what molecules are proposed as plausible candidates to encode the 'credit' values?",
        "What is the key mathematical conclusion proven in the paper regarding the proposed neuroplasticity rule in layered neural networks?"
    ]
    
    reference_answers = [
        "The three main problems are the weight symmetry problem, the update locking problem, and the derivative computation problem.",
        "The three timescales are: neural firing on the millisecond scale for computation, credit redistribution (retrograde signaling) on the seconds scale for credit assignment, and neural plasticity from seconds to minutes for weight updates.",
        "Neurotrophic factors (NTFs), which are retrograde messengers, are proposed as plausible candidates to encode the credit values.",
        "The paper mathematically proves that in layered neural networks, the proposed neuroplasticity rule precisely replicates (or reduces exactly to) the backpropagation algorithm without any approximations."
    ]

    data_for_ragas = {
        "question": [], "answer": [], "contexts": [], "reference": []
    }

    async with AsyncSessionLocal() as db_session:
        for idx, question in enumerate(test_questions):
            print(f"\nEvaluating: '{question}'")
            try:
                query_embedding = await qp_service._generate_query_embedding(question)

                chunks = await vector_service.query_documents(
                    query_text=question, query_embedding=query_embedding,
                    n_results=4, allowed_doc_ids=[doc_id], db_session=db_session
                )
                context_texts = [chunk["text_chunk"] for chunk in chunks]

                consolidated_context = "\n\n".join(context_texts)
                prompt = f"""
                Based ONLY on the following context, answer the user's question.
                Context: {consolidated_context}
                Question: {question}
                """
                response = await groq_llm.ainvoke([HumanMessage(content=prompt)])
                answer = response.content

                data_for_ragas["question"].append(question)
                data_for_ragas["answer"].append(answer)
                data_for_ragas["contexts"].append(context_texts)
                data_for_ragas["reference"].append(reference_answers[idx])

                await asyncio.sleep(2) 

            except Exception as e:
                print(f"Error on question '{question}': {e}")
                data_for_ragas["question"].append(question)
                data_for_ragas["answer"].append("Error")
                data_for_ragas["contexts"].append([""])
                data_for_ragas["reference"].append(reference_answers[idx])

    print("\n Handing over to RAGAS LLM-as-a-Judge (Groq Llama-3)...")
    
    gemini_embeddings = GoogleGenerativeAIEmbeddings(
        model=f"models/{settings.google_genai_embedding_model_id}", 
        google_api_key=settings.google_genai_api_key
    )

    hf_dataset = Dataset.from_dict(data_for_ragas)

    safe_config = RunConfig(max_workers=2, max_retries=5, max_wait=30)

    result = evaluate(
        hf_dataset,
        metrics=[ContextPrecision(), Faithfulness(), AnswerRelevancy()],
        llm=groq_llm,
        embeddings=gemini_embeddings,
        run_config=safe_config,
        raise_exceptions=False
    )

    df = result.to_pandas()
    
    print("\n================ RAGBENCH RESULTS ================")
    print(f"Overall Faithfulness:     {df['faithfulness'].mean():.2f} / 1.0")
    print(f"Overall Answer Relevancy: {df['answer_relevancy'].mean():.2f} / 1.0")
    print(f"Overall Context Precision:{df['context_precision'].mean():.2f} / 1.0")
    print("==================================================\n")
    
    df.to_csv("ragbench_results.csv", index=False)
    print("Detailed report saved to ragbench_results.csv")

if __name__ == "__main__":
    TARGET_DOC_ID = "" #<---- change this before running the eval
    asyncio.run(run_benchmark(TARGET_DOC_ID))