"""
Proof Submission Handler

Handles proof submission and verification for challenges.
Users can submit photos or text descriptions as proof of completion.
"""

import os
import logging
from datetime import datetime
from typing import Dict, Any, Optional, Tuple
import asyncio

from ai.gemini_client import GeminiClient
from services.supabase_client import SupabaseClient
from api.whatsapp_mcp import WhatsAppMCPClient
from utils.logger import setup_logger
from utils.retry import with_retry

logger = setup_logger(__name__)

class ProofHandler:
    """Handles proof submission and AI verification for challenges."""
    
    def __init__(self):
        self.supabase = SupabaseClient()
        self.gemini = GeminiClient()
        self.whatsapp = WhatsAppMCPClient()
        
        logger.info("Proof handler initialized")
    
    @with_retry(max_retries=3, delay=1.0)
    async def handle_proof_submission(
        self, 
        user_id: str, 
        phone_number: str,
        challenge_id: str,
        proof_content: str,
        media_url: Optional[str] = None
    ) -> str:
        """
        Handle submission of proof for a challenge.
        
        Args:
            user_id: User submitting proof
            phone_number: User's phone number
            challenge_id: Challenge being completed
            proof_content: Text description of proof
            media_url: Optional media file URL
            
        Returns:
            str: Response message to send back to user
        """
        try:
            # Get challenge details
            challenge = await self.supabase.get_challenge_by_id(challenge_id)
            if not challenge:
                return "❌ Challenge not found. Please check the challenge ID and try again."
            
            # Verify user owns this challenge
            if challenge["user_id"] != user_id:
                return "❌ You can only submit proof for your own challenges."
            
            # Check if challenge is still active
            if challenge["status"] != "active":
                return f"❌ This challenge is already {challenge['status']}. You can only submit proof for active challenges."
            
            # Check if deadline hasn't passed
            deadline = datetime.fromisoformat(challenge["deadline"])
            if datetime.now() > deadline:
                return "⏰ Sorry, the deadline for this challenge has passed. The challenge will be marked as failed."
            
            # Create submission record
            submission = await self.supabase.create_task_submission(
                challenge_id=challenge_id,
                user_id=user_id,
                proof_url=media_url,
                description=proof_content
            )
            
            # Verify proof with AI
            verification_result = await self._verify_proof_with_ai(
                challenge, proof_content, media_url
            )
            
            # Update submission with verification result
            await self.supabase.update_submission_verification(
                submission["id"],
                verified=verification_result["verified"],
                ai_verdict=verification_result["verdict"],
                image_metadata=verification_result.get("metadata")
            )
            
            # Process verification result
            if verification_result["verified"]:
                return await self._handle_successful_verification(
                    user_id, phone_number, challenge, submission
                )
            else:
                return await self._handle_failed_verification(
                    user_id, phone_number, challenge, verification_result
                )
                
        except Exception as e:
            logger.error(f"Error handling proof submission: {e}")
            return "❌ An error occurred while processing your proof. Please try again later."
    
    async def _verify_proof_with_ai(
        self, 
        challenge: Dict[str, Any], 
        proof_content: str,
        media_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Verify proof using Gemini AI.
        
        Args:
            challenge: Challenge data
            proof_content: Text proof description  
            media_url: Optional image/media URL
            
        Returns:
            dict: Verification result with verdict and confidence
        """
        try:
            challenge_title = challenge["title"]
            verification_method = challenge.get("verification_method", "photo")
            verification_details = challenge.get("verification_details", "")
            
            if media_url and verification_method == "photo":
                # Use image verification
                result = await self.gemini.verify_image_proof(
                    image_path=media_url,
                    challenge_description=challenge_title,
                    expected_proof=verification_details,
                    additional_context=proof_content
                )
            else:
                # Use text-only verification
                result = await self.gemini.verify_text_proof(
                    challenge_description=challenge_title,
                    proof_description=proof_content,
                    expected_proof=verification_details
                )
            
            logger.info(f"AI verification result for challenge {challenge['id']}: {result['verdict']}")
            return result
            
        except Exception as e:
            logger.error(f"Error in AI verification: {e}")
            # Fallback to manual review
            return {
                "verified": False,
                "verdict": f"AI verification failed ({str(e)}). Manual review required.",
                "confidence": 0.0,
                "requires_manual_review": True
            }
    
    async def _handle_successful_verification(
        self, 
        user_id: str,
        phone_number: str, 
        challenge: Dict[str, Any],
        submission: Dict[str, Any]
    ) -> str:
        """
        Handle successful proof verification.
        
        Args:
            user_id: User ID
            phone_number: User's phone number
            challenge: Challenge data
            submission: Submission data
            
        Returns:
            str: Success message
        """
        try:
            challenge_id = challenge["id"]
            amount = challenge["amount"]
            
            # Mark challenge as completed
            await self.supabase.update_challenge_status(challenge_id, "completed")
            
            # Calculate reward (return bet + bonus)
            bonus_percentage = 0.1  # 10% bonus for completion
            reward_amount = amount * (1 + bonus_percentage)
            
            # Update user balance
            current_balance = await self.supabase.get_user_balance(user_id)
            new_balance = current_balance + reward_amount
            await self.supabase.update_user_balance(user_id, new_balance)
            
            # Record reward transaction
            await self.supabase.record_transaction(
                user_id=user_id,
                amount=reward_amount,
                transaction_type="reward",
                description=f"Challenge completed: {challenge['title']}",
                challenge_id=challenge_id
            )
            
            # Send success notification
            message = f"""🎉 CHALLENGE COMPLETED! 🎉

✅ Your proof has been verified and accepted!

📝 Challenge: "{challenge['title']}"
💰 Reward: ₹{reward_amount:.2f} (₹{amount} stake + ₹{reward_amount - amount:.2f} bonus)
💳 New Balance: ₹{new_balance:.2f}

Congratulations on staying committed! 🌟

Want to keep the momentum going? Send "create challenge" to start a new one!"""

            logger.info(f"Challenge {challenge_id} completed successfully by user {user_id}")
            return message
            
        except Exception as e:
            logger.error(f"Error handling successful verification: {e}")
            return "✅ Your proof was verified, but there was an error processing the reward. Please contact support."
    
    async def _handle_failed_verification(
        self, 
        user_id: str,
        phone_number: str,
        challenge: Dict[str, Any], 
        verification_result: Dict[str, Any]
    ) -> str:
        """
        Handle failed proof verification.
        
        Args:
            user_id: User ID
            phone_number: User's phone number
            challenge: Challenge data
            verification_result: AI verification result
            
        Returns:
            str: Failure message with guidance
        """
        try:
            verdict = verification_result.get("verdict", "Proof not sufficient")
            requires_manual_review = verification_result.get("requires_manual_review", False)
            
            if requires_manual_review:
                message = f"""⚠️ MANUAL REVIEW REQUIRED

Your proof submission needs human review:

📝 Challenge: "{challenge['title']}"
🤖 AI Verdict: {verdict}

Your submission has been flagged for manual review. You'll receive an update within 24 hours.

In the meantime, you can still submit additional proof if you have it!"""

                # TODO: Implement manual review queue
                logger.info(f"Challenge {challenge['id']} flagged for manual review")
                
            else:
                message = f"""❌ PROOF NOT ACCEPTED

Your proof submission was not sufficient:

📝 Challenge: "{challenge['title']}"
🤖 AI Feedback: {verdict}

💡 Tips for better proof:
• Take clearer photos showing the completed task
• Provide more detailed descriptions
• Make sure the image matches your challenge requirements

You can submit new proof anytime before the deadline. Just send another photo or description!"""

            return message
            
        except Exception as e:
            logger.error(f"Error handling failed verification: {e}")
            return "❌ Your proof was not accepted. Please try submitting clearer evidence of completion."
    
    async def handle_proof_resubmission(
        self, 
        user_id: str,
        phone_number: str, 
        challenge_id: str,
        new_proof_content: str,
        new_media_url: Optional[str] = None
    ) -> str:
        """
        Handle resubmission of proof for a challenge.
        
        Args:
            user_id: User resubmitting proof
            phone_number: User's phone number
            challenge_id: Challenge ID
            new_proof_content: New proof description
            new_media_url: New media URL
            
        Returns:
            str: Response message
        """
        try:
            # Check if challenge allows resubmission
            challenge = await self.supabase.get_challenge_by_id(challenge_id)
            if not challenge:
                return "❌ Challenge not found."
            
            if challenge["status"] == "completed":
                return "✅ This challenge is already completed!"
            
            if challenge["status"] == "failed":
                return "❌ This challenge has already failed. You cannot resubmit proof."
            
            # Check deadline
            deadline = datetime.fromisoformat(challenge["deadline"])
            if datetime.now() > deadline:
                return "⏰ The deadline has passed. You cannot resubmit proof."
            
            # Handle as new proof submission
            return await self.handle_proof_submission(
                user_id, phone_number, challenge_id, 
                new_proof_content, new_media_url
            )
            
        except Exception as e:
            logger.error(f"Error handling proof resubmission: {e}")
            return "❌ An error occurred while processing your resubmission."
    
    def get_proof_submission_guidance(self, challenge: Dict[str, Any]) -> str:
        """
        Generate guidance message for proof submission.
        
        Args:
            challenge: Challenge data
            
        Returns:
            str: Guidance message
        """
        verification_method = challenge.get("verification_method", "photo")
        verification_details = challenge.get("verification_details", "")
        
        if verification_method == "photo":
            guidance = f"""📸 PROOF SUBMISSION GUIDE

For challenge: "{challenge['title']}"

📋 How to submit proof:
• Take a clear photo showing completion
• Send the photo with a brief description
• Make sure the image clearly shows: {verification_details if verification_details else "the completed task"}

💡 Tips for acceptance:
• Good lighting and clear visibility
• Include yourself in the photo if relevant
• Show before/after if applicable
• Add context in your message

Just send the photo when ready! 📱"""
        else:
            guidance = f"""✍️ PROOF SUBMISSION GUIDE

For challenge: "{challenge['title']}"

📋 How to submit proof:
• Send a detailed description of completion
• Include specific details about what you did
• {verification_details if verification_details else "Be specific and honest"}

💡 Tips for acceptance:
• Be specific about actions taken
• Include timestamps if relevant
• Mention any measurable results
• Be honest and detailed

Just send your description when ready! 💬"""
        
        return guidance 