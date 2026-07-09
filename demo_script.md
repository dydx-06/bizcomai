# End-to-End Demo Script: AI Business Companion

## Slide 1: Introduction
**Speaker:** Welcome to the final demo of the AI Business Companion. Our goal was to build a multilingual, voice-enabled AI platform that helps Indian MSME owners understand their business data and discover government schemes.
*Action:* Display the Dashboard page.

## Slide 2: Document Intelligence
**Speaker:** The first step is providing context to the AI. MSME owners can upload their business documents securely.
*Action:* Navigate to the Document Hub. Select "Udyam Registration" and click "Upload Document".
*Expected outcome:* The system processes the document and generates vector embeddings. (Simulated via `/api/documents/upload`).

## Slide 3: Cashflow & Scheme Matching
**Speaker:** With the documents processed, our transaction parser and scheme matching engine evaluate the business profile. Let's see what schemes this business qualifies for.
*Action:* Navigate to the Scheme Matcher. Click "Recalculate Matches".
*Expected outcome:* The page displays "Credit Guarantee Fund Trust for Micro and Small Enterprises (CGTMSE)" with a 95% match score. (Simulated via `/api/schemes/match`).

## Slide 4: AI Voice Advisor
**Speaker:** Finally, the most powerful feature for non-technical users is our multilingual AI advisor.
*Action:* Navigate to the AI Advisor. Type or simulate speaking: "What schemes do I qualify for based on my Udyam certificate?"
*Expected outcome:* The AI (simulated via `/api/qa/ask`) responds with grounded answers, verifying eligibility for the CGTMSE scheme.

## Conclusion
**Speaker:** This end-to-end flow proves our core hypothesis: MSME owners can get personalized, data-backed consulting using just their voice and existing business documents. Thank you!
