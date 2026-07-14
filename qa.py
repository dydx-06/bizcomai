import os
from dotenv import load_dotenv
import google.generativeai as genai
import voice_module

load_dotenv()


class QAEngine:

    def __init__(self):
        genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
        self.model = genai.GenerativeModel("gemini-2.5-flash")

    def build_context(self, chunks):
        context = ""

        for chunk in chunks:
            context += (
                f"\n(Page {chunk['page']})\n"
                f"{chunk['text']}\n"
            )

        return context

    def ask(self, question, retrieved_chunks, lang_choice="en"):

        context = self.build_context(retrieved_chunks)

        prompt = f"""
        You are an AI assistant helping Indian MSMEs.

        Answer ONLY using the context below.

        If the answer is not present in the context, reply exactly:

        "I could not find the answer in the uploaded document."

        Context:
        ----------------------
        {context}
        ----------------------

        Question:
        {question}

        Answer:
        """

        response = self.model.generate_content(prompt)

        answer = response.text

        # Speak the answer using Azure Speech
        voice_module.speak_text(answer, lang_choice)

        return answer