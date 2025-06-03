"""
Fund Addition Handler

Manages fund addition to user wallets including:
- UPI payment processing
- Transaction verification
- Wallet balance updates
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta

from services.supabase_client import SupabaseClient
from utils.logger import setup_logger

logger = setup_logger(__name__)

class FundHandler:
    """Handler for fund addition and UPI payments."""
    
    def __init__(self, supabase_client: SupabaseClient):
        self.supabase_client = supabase_client
        # Store fund addition state for users in progress
        self.fund_state = {}
        # Store payment screenshot waiting state
        self.payment_screenshot_state = {}
    
    async def handle_add_funds(
        self, 
        user_id: str, 
        phone_number: str, 
        message: str
    ) -> str:
        """
        Handle fund addition request.
        
        Args:
            user_id: User ID
            phone_number: User's WhatsApp number
            message: User's input message
            
        Returns:
            str: Response message
        """
        try:
            # Check if user is already in fund addition flow
            if phone_number in self.fund_state:
                return await self._continue_fund_addition(phone_number, message)
            else:
                return await self._start_fund_addition(phone_number, user_id)
                
        except Exception as e:
            logger.error(f"Error in fund addition flow: {e}")
            return "❌ Sorry, there was an error processing your fund addition request. Please try again."
    
    async def _start_fund_addition(self, phone_number: str, user_id: str) -> str:
        """Start the fund addition process."""
        self.fund_state[phone_number] = {
            "step": "amount",
            "user_id": user_id,
            "phone": phone_number,
            "started_at": datetime.now()
        }
        
        return (
            "💰 **Add Funds to Wallet**\n\n"
            "How much would you like to add to your wallet?\n"
            "Enter amount in ₹ (minimum ₹50, maximum ₹50,000):\n\n"
            "Example: 100, 500, 1000"
        )
    
    async def _continue_fund_addition(self, phone_number: str, message: str) -> str:
        """Continue with the fund addition process."""
        state = self.fund_state[phone_number]
        step = state["step"]
        
        if step == "amount":
            return await self._handle_amount_step(phone_number, message)
        elif step == "confirm":
            return await self._handle_confirmation_step(phone_number, message)
        else:
            # Invalid state, restart
            del self.fund_state[phone_number]
            return await self._start_fund_addition(phone_number, state["user_id"])
    
    async def _handle_amount_step(self, phone_number: str, amount_str: str) -> str:
        """Handle amount input step."""
        try:
            # Clean and parse amount - handle various formats
            amount_str = amount_str.lower().strip()
            
            # Remove common words and symbols
            amount_str = amount_str.replace("₹", "").replace("rs", "").replace("rupees", "").replace("inr", "")
            amount_str = amount_str.replace(",", "").replace(" ", "").strip()
            
            # Extract numbers from the string
            import re
            numbers = re.findall(r'\d+\.?\d*', amount_str)
            
            if not numbers:
                return "❌ Please enter a valid amount (numbers only). Example: 100, 500, 1000"
            
            amount = float(numbers[0])
            
            if amount < 50:
                return "❌ Minimum amount is ₹50. Please enter a higher amount:"
            
            if amount > 50000:
                return "❌ Maximum amount is ₹50,000. Please enter a lower amount:"
            
            # Save amount and move to confirmation step
            self.fund_state[phone_number]["amount"] = amount
            self.fund_state[phone_number]["step"] = "confirm"
            
            return (
                f"💰 **Fund Addition Summary**\n\n"
                f"Amount: ₹{amount:,.2f}\n"
                f"Payment Method: UPI\n"
                f"UPI ID: devtalele0@okhdfcbank\n\n"
                "Type 'confirm' to proceed with payment, or 'cancel' to abort:"
            )
            
        except (ValueError, IndexError):
            return "❌ Please enter a valid amount (numbers only). Example: 100, 500, 1000"
    
    async def _handle_confirmation_step(self, phone_number: str, message: str) -> str:
        """Handle confirmation step."""
        message_lower = message.lower().strip()
        
        if message_lower == "confirm":
            state = self.fund_state[phone_number]
            amount = state["amount"]
            user_id = state["user_id"]
            
            # Create payment request
            payment_request = await self._create_payment_request(user_id, amount)
            
            # Move user to payment screenshot waiting state
            self.payment_screenshot_state[phone_number] = {
                "user_id": user_id,
                "amount": amount,
                "payment_id": payment_request["id"],
                "waiting_since": datetime.now()
            }
            
            # Clean up fund addition state
            del self.fund_state[phone_number]
            
            # Send UPI QR code and instructions
            return await self._generate_upi_payment_response(amount, payment_request["id"])
            
        elif message_lower == "cancel":
            del self.fund_state[phone_number]
            return "❌ Fund addition cancelled. You can start again by typing 'add funds'."
        else:
            return "Please type 'confirm' to proceed or 'cancel' to abort the fund addition:"
    
    async def _create_payment_request(self, user_id: str, amount: float) -> Dict[str, Any]:
        """Create payment request in database."""
        try:
            payment_data = {
                "user_id": user_id,
                "amount": amount,
                "status": "pending",
                "payment_method": "upi",
                "created_at": datetime.now().isoformat(),
                "expires_at": (datetime.now()).isoformat()  # 24 hour expiry
            }
            
            result = self.supabase_client.client.table("payment_requests").insert(payment_data).execute()
            
            if result.data:
                logger.info(f"Created payment request for user {user_id}, amount ₹{amount}")
                return result.data[0]
            else:
                raise Exception("Failed to create payment request")
                
        except Exception as e:
            logger.error(f"Error creating payment request: {e}")
            raise
    
    async def _generate_upi_payment_response(self, amount: float, payment_id: str) -> str:
        """Generate UPI payment response with QR code."""
        return (
            f"💳 **Payment Required: ₹{amount:,.2f}**\n\n"
            "📱 I'll send you the UPI QR code in the next message.\n\n"
            "💡 **Payment Details:**\n"
            f"• UPI ID: devtalele0@okhdfcbank\n"
            f"• Amount: ₹{amount:,.2f}\n"
            f"• Reference: PAY{payment_id[:8]}\n\n"
            "⚠️ **After Payment:**\n"
            "1. Send a screenshot of the successful transaction\n"
            "2. Your wallet will be credited within 5 minutes\n"
            "3. You'll receive a confirmation message\n\n"
            "🕐 This payment link expires in 24 hours."
        )
    
    async def handle_payment_screenshot(
        self, 
        user_id: str, 
        phone_number: str, 
        image_data: bytes
    ) -> str:
        """
        Handle payment screenshot verification using Gemini AI.
        
        Args:
            user_id: User ID
            phone_number: User's phone number
            image_data: Screenshot image data
            
        Returns:
            str: Response message
        """
        try:
            logger.info(f"🔍 Processing payment screenshot for user {user_id} ({phone_number})")
            
            # Basic validation first
            if len(image_data) < 1000:  # Very small file
                return (
                    "❌ **Invalid Image File**\n\n"
                    "The image file appears to be too small or corrupted.\n\n"
                    "💡 **Please:**\n"
                    "1. Take a clear screenshot of your payment confirmation\n"
                    "2. Make sure the image is saved properly\n"
                    "3. Try sending it again\n\n"
                    "The file should be at least a few KB in size."
                )
            
            if len(image_data) > 10 * 1024 * 1024:  # Very large file (>10MB)
                return (
                    "❌ **Image File Too Large**\n\n"
                    "The image file is too large to process.\n\n"
                    "💡 **Please:**\n"
                    "1. Compress the image or take a new screenshot\n"
                    "2. Ensure the file is under 10MB\n"
                    "3. Send the compressed image\n\n"
                    "A simple screenshot should be much smaller."
                )
            
            # Get pending payment requests for this user
            pending_payments = await self._get_pending_payments(user_id)
            
            # Check if user is in payment screenshot waiting state
            payment_info = self.get_payment_screenshot_info(phone_number)
            if payment_info:
                expected_amount = payment_info["amount"]
                logger.info(f"📱 User in payment screenshot waiting state, expected amount: ₹{expected_amount}")
            else:
                logger.info(f"📋 Found {len(pending_payments)} pending payments")
            
            if not pending_payments and not payment_info:
                # Try to find ANY pending payment in the last 24 hours and assign to this user
                logger.info("🔄 No user-specific payments found, checking all recent payments")
                
                yesterday = (datetime.now() - timedelta(hours=24)).strftime('%Y-%m-%d %H:%M:%S')
                
                result = self.supabase_client.client.table("payment_requests").select("*").eq(
                    "status", "pending"
                ).gte("created_at", yesterday).order("created_at", desc=True).limit(5).execute()
                
                all_pending = result.data or []
                logger.info(f"🔍 Found {len(all_pending)} total pending payments in last 24h")
                
                if all_pending:
                    # Use the most recent one and update it to this user
                    payment_request = all_pending[0]
                    logger.info(f"🔄 Assigning payment {payment_request['id'][:8]}... to user {user_id}")
                    
                    # Update the payment to this user
                    self.supabase_client.client.table("payment_requests").update({
                        "user_id": user_id
                    }).eq("id", payment_request["id"]).execute()
                    
                    payment_request["user_id"] = user_id  # Update local copy
                    expected_amount = payment_request["amount"]
                else:
                    return (
                        "❌ **No Payment Request Found**\n\n"
                        "I couldn't find any recent payment requests to verify against.\n\n"
                        "💡 **Please:**\n"
                        "1. Start with 'add funds' command first\n"
                        "2. Make the UPI payment within 24 hours\n"
                        "3. Then send the payment screenshot\n\n"
                        "Type 'add funds' to create a new payment request."
                    )
            else:
                # Use payment info if available, otherwise use the most recent payment request
                if payment_info:
                    # Find the specific payment request for this payment info
                    result = self.supabase_client.client.table("payment_requests").select("*").eq(
                        "id", payment_info["payment_id"]
                    ).execute()
                    
                    if result.data:
                        payment_request = result.data[0]
                        expected_amount = payment_info["amount"]
                    else:
                        # Fallback to pending payments
                        payment_request = pending_payments[0] if pending_payments else None
                        expected_amount = payment_request["amount"] if payment_request else 0
                else:
                    # Use the most recent payment request
                    payment_request = pending_payments[0]
                    expected_amount = payment_request["amount"]
                    
                logger.info(f"💳 Using payment request {payment_request['id'][:8]}... for ₹{expected_amount}")
            
            # Store screenshot for records first
            try:
                screenshot_url = await self._store_payment_screenshot(
                    payment_request["id"], image_data
                )
                logger.info(f"📸 Screenshot stored at: {screenshot_url}")
            except Exception as storage_error:
                logger.error(f"Failed to store screenshot: {storage_error}")
                return (
                    "❌ **Screenshot Storage Failed**\n\n"
                    f"Technical error: {str(storage_error)}\n\n"
                    "💡 **Please:**\n"
                    "1. Check your internet connection\n"
                    "2. Try sending the screenshot again\n"
                    "3. Contact support if the issue persists\n\n"
                    "The issue might be temporary."
                )
            
            # Clear payment screenshot waiting state
            self.clear_payment_screenshot_state(phone_number)
            
            # Now use Gemini AI to verify the payment screenshot
            logger.info(f"🤖 Starting AI verification for ₹{expected_amount} payment")
            
            try:
                # Import and use GeminiClient for verification
                from ai.gemini_client import GeminiClient
                gemini_client = GeminiClient()
                
                # Check if Gemini is available
                if not gemini_client.api_key:
                    logger.warning("Gemini API not available, using manual review")
                    # Update payment request to mark for manual review
                    self.supabase_client.client.table("payment_requests").update({
                        "status": "pending"
                    }).eq("id", payment_request["id"]).execute()
                    
                    return (
                        f"🔍 **Payment Under Manual Review**\n\n"
                        f"💰 Expected Amount: ₹{expected_amount:,.2f}\n"
                        f"🏦 Expected UPI: devtalele0@okhdfcbank\n\n"
                        "Your payment screenshot has been received and is being reviewed by our team.\n\n"
                        "**Why manual review?**\n"
                        "• AI verification system is currently unavailable\n"
                        "• All payments require human verification for security\n\n"
                        "⏰ You'll receive confirmation within 24 hours.\n"
                        "If urgent, please contact support."
                    )
                
                verification_result = await gemini_client.verify_payment_screenshot(
                    image_data=image_data,
                    expected_amount=expected_amount,
                    expected_upi_id="devtalele0@okhdfcbank",
                    payment_time_window_hours=24
                )
                
                logger.info(f"🔍 AI verification result: {verification_result}")
                
            except Exception as ai_error:
                logger.error(f"AI verification failed: {ai_error}")
                
                # Update payment request to mark for manual review
                self.supabase_client.client.table("payment_requests").update({
                    "status": "pending"
                }).eq("id", payment_request["id"]).execute()
                
                return (
                    f"🔍 **Payment Under Manual Review**\n\n"
                    f"💰 Expected Amount: ₹{expected_amount:,.2f}\n"
                    f"🏦 Expected UPI: devtalele0@okhdfcbank\n\n"
                    f"**Technical Issue:** {str(ai_error)[:100]}...\n\n"
                    "Your payment screenshot has been received and is being reviewed by our team.\n\n"
                    "**Why manual review?**\n"
                    "• AI verification encountered a technical error\n"
                    "• Manual verification ensures accuracy\n\n"
                    "⏰ You'll receive confirmation within 24 hours.\n"
                    "If urgent, please contact support."
                )
            
            # Process verification result
            suggested_action = verification_result.get("suggested_action", "manual_review")
            amount_paid = verification_result.get("amount_paid", 0.0)
            verdict = verification_result.get("verdict", "No verdict provided")
            confidence = verification_result.get("confidence", 0.0)
            concerns = verification_result.get("concerns", [])
            recipient_upi = verification_result.get("recipient_upi", "")
            transaction_status = verification_result.get("transaction_status", "UNKNOWN")
            timestamp_valid = verification_result.get("timestamp_valid", False)
            amount_matches = verification_result.get("amount_matches", False)
            upi_matches = verification_result.get("upi_matches", False)
            
            logger.info(f"💰 Suggested action: {suggested_action}, Amount paid: ₹{amount_paid}")
            
            if suggested_action == "credit_full":
                # Credit the full expected amount (amount matches exactly or very close)
                credit_amount = expected_amount
                success = await self._approve_payment(payment_request["id"], user_id, credit_amount)
                
                if success:
                    # Get current balance AFTER payment approval to show updated balance
                    current_balance = await self.supabase_client.get_user_balance(user_id)
                    
                    # Clear any payment screenshot waiting state
                    self.clear_payment_screenshot_state(phone_number)
                    
                    # Check if this is the user's first successful payment (new user onboarding)
                    user_transactions = await self.supabase_client.get_user_transactions(user_id, limit=2)
                    is_first_payment = len([t for t in user_transactions if t.get('transaction_type') == 'deposit']) == 1
                    
                    if is_first_payment:
                        # First payment - provide comprehensive onboarding
                        return (
                            f"✅ Payment Verified & Wallet Credited!\n\n"
                            f"💰 Amount: ₹{credit_amount:,.2f}\n"
                            f"💳 New Balance: ₹{current_balance:,.2f}\n\n"
                            f"🎉 Welcome to BetTask!\n\n"
                            f"📋 How to create challenges:\n"
                            f"• Text: 'I will go to gym today, bet ₹100'\n"
                            f"• Or: 'I want to read 20 pages'\n"
                            f"• Then specify bet amount\n\n"
                            f"📸 Submit proof:\n"
                            f"• Use web app: dare-you-succeed.vercel.app\n"
                            f"• Better verification & instant results\n\n"
                            f"💡 Commands:\n"
                            f"• 'balance' - Check wallet\n"
                            f"• 'my challenges' - View active challenges\n"
                            f"• 'history' - Transaction history\n"
                            f"• 'help' - All commands\n\n"
                            f"🚀 Ready to start your first challenge?"
                        )
                    else:
                        # Regular payment confirmation
                        return (
                            f"✅ Payment Verified & Wallet Credited!\n\n"
                            f"💰 Amount: ₹{credit_amount:,.2f}\n"
                            f"💳 New Balance: ₹{current_balance:,.2f}\n\n"
                            f"🎯 Ready to create more challenges?\n\n"
                            f"💡 Quick commands:\n"
                            f"• 'I will [goal], bet ₹[amount]'\n"
                            f"• 'my challenges' - View active\n"
                            f"• 'balance' - Check wallet"
                        )
                else:
                    logger.error(f"❌ Failed to approve payment {payment_request['id']}")
                    return (
                        "⚠️ **Verification Successful but Credit Failed**\n\n"
                        "Your payment was verified but there was a technical issue crediting your wallet.\n"
                        "Our team has been notified and will manually credit your account within 24 hours.\n\n"
                        "Please contact support if you don't see the credit soon."
                    )
            
            elif suggested_action == "credit_partial":
                # Credit the actual amount paid (which is different from expected - this is the user's request!)
                credit_amount = amount_paid  # Always use the amount found in screenshot
                
                if credit_amount >= 50:  # Minimum amount check
                    success = await self._approve_payment(payment_request["id"], user_id, credit_amount)
                    
                    if success:
                        amount_difference = expected_amount - credit_amount
                        logger.info(f"✅ Actual amount credited - ₹{credit_amount} (expected ₹{expected_amount})")
                        
                        if credit_amount > expected_amount:
                            return (
                                f"✅ **Payment Verified & Wallet Credited!**\n\n"
                                f"💰 **Amount Credited: ₹{credit_amount:,.2f}**\n"
                                f"📊 Expected: ₹{expected_amount:,.2f}\n"
                                f"🎁 **Bonus: ₹{credit_amount - expected_amount:,.2f}**\n"
                                f"🏦 Paid to: {recipient_upi}\n"
                                f"🤖 AI Confidence: {confidence:.1%}\n\n"
                                f"📝 **AI Analysis:** {verdict}\n\n"
                                f"🎉 **You paid extra!** Your wallet has been credited with the full amount you actually paid (₹{credit_amount:,.2f}).\n\n"
                                "✨ Thank you for the extra contribution! You can now create challenges!"
                            )
                        elif credit_amount < expected_amount:
                            return (
                                f"✅ **Payment Verified & Wallet Credited!**\n\n"
                                f"💰 **Amount Credited: ₹{credit_amount:,.2f}**\n"
                                f"📊 Expected: ₹{expected_amount:,.2f}\n"
                                f"📉 Difference: ₹{abs(amount_difference):,.2f} less\n"
                                f"🏦 Paid to: {recipient_upi}\n"
                                f"🤖 AI Confidence: {confidence:.1%}\n\n"
                                f"📝 **AI Analysis:** {verdict}\n\n"
                                f"✅ **Your wallet has been credited with the exact amount you paid (₹{credit_amount:,.2f}).**\n\n"
                                f"💡 If you want to add the remaining ₹{abs(amount_difference):,.2f}, you can type 'add funds' again."
                            )
                        else:
                            # Amounts are equal
                            return (
                                f"✅ **Payment Verified & Wallet Credited!**\n\n"
                                f"💰 **Amount Credited: ₹{credit_amount:,.2f}**\n"
                                f"🏦 Paid to: {recipient_upi}\n"
                                f"🤖 AI Confidence: {confidence:.1%}\n\n"
                                f"📝 **AI Analysis:** {verdict}\n\n"
                                f"🎉 Perfect! Your wallet has been credited with the exact amount you paid.\n"
                                "You can now create challenges!"
                            )
                    else:
                        return (
                            "⚠️ **Verification Successful but Credit Failed**\n\n"
                            "Your payment was verified but there was a technical issue.\n"
                            "Please contact support for manual processing."
                        )
                else:
                    return (
                        f"❌ **Payment Amount Too Low**\n\n"
                        f"💰 Amount Detected: ₹{credit_amount:,.2f}\n"
                        f"📊 Expected: ₹{expected_amount:,.2f}\n"
                        f"🚫 Minimum Required: ₹50.00\n"
                        f"🏦 Recipient UPI: {recipient_upi}\n\n"
                        f"🤖 AI Analysis: {verdict}\n\n"
                        "Please make a payment of at least ₹50 and send a new screenshot."
                    )
            
            elif suggested_action == "reject":
                # Payment failed verification - provide detailed reasons
                concerns_text = "\n".join([f"• {concern}" for concern in concerns]) if concerns else "• General verification failure"
                
                # Mark payment as failed
                self.supabase_client.client.table("payment_requests").update({
                    "status": "rejected"
                }).eq("id", payment_request["id"]).execute()
                
                logger.info(f"❌ Payment rejected: {verdict}")
                
                return (
                    f"❌ **Payment Verification Failed**\n\n"
                    f"💰 Expected Amount: ₹{expected_amount:,.2f}\n"
                    f"💰 Amount Found: ₹{amount_paid:,.2f}\n"
                    f"🏦 Expected UPI: devtalele0@okhdfcbank\n"
                    f"🏦 Found UPI: {recipient_upi}\n"
                    f"📅 Time Valid: {'✅' if timestamp_valid else '❌'}\n"
                    f"💰 Amount Match: {'✅' if amount_matches else '❌'}\n"
                    f"🏦 UPI Match: {'✅' if upi_matches else '❌'}\n"
                    f"📊 Status: {transaction_status}\n\n"
                    f"🤖 **AI Analysis:** {verdict}\n\n"
                    f"⚠️ **Specific Issues Found:**\n{concerns_text}\n\n"
                    "💡 **To Fix This:**\n"
                    "1. Ensure you paid to: devtalele0@okhdfcbank\n"
                    f"2. Payment amount should be: ₹{expected_amount:,.2f}\n"
                    "3. Payment should be successful (not failed/pending)\n"
                    "4. Send a clear, complete screenshot\n"
                    "5. Payment should be recent (within 24 hours)\n\n"
                    "Type 'add funds' to start a new payment request if needed."
                )
            
            else:
                # Manual review required - provide detailed reasons
                concerns_text = "\n".join([f"• {concern}" for concern in concerns]) if concerns else "• Requires human verification"
                
                logger.info(f"🔍 Payment requires manual review: {verdict}")
                
                # Update payment request to mark for manual review
                self.supabase_client.client.table("payment_requests").update({
                    "status": "pending"
                }).eq("id", payment_request["id"]).execute()
                
                return (
                    f"🔍 **Payment Under Manual Review**\n\n"
                    f"💰 Expected Amount: ₹{expected_amount:,.2f}\n"
                    f"💰 Amount Found: ₹{amount_paid:,.2f}\n"
                    f"🏦 Expected UPI: devtalele0@okhdfcbank\n"
                    f"🏦 Found UPI: {recipient_upi}\n"
                    f"📅 Time Valid: {'✅' if timestamp_valid else '❌'}\n"
                    f"💰 Amount Match: {'✅' if amount_matches else '❌'}\n"
                    f"🏦 UPI Match: {'✅' if upi_matches else '❌'}\n"
                    f"🤖 Confidence: {confidence:.1%}\n\n"
                    f"🤖 **AI Analysis:** {verdict}\n\n"
                    f"📋 **Review Reasons:**\n{concerns_text}\n\n"
                    "Your payment screenshot has been received and is being reviewed by our team.\n\n"
                    "⏰ You'll receive confirmation within 24 hours.\n"
                    "If urgent, please contact support."
                )
                
        except Exception as e:
            logger.error(f"❌ Error processing payment screenshot: {e}")
            import traceback
            traceback.print_exc()
            
            # Provide more specific error information
            error_type = type(e).__name__
            error_details = str(e)
            
            return (
                f"❌ **Payment Processing Error**\n\n"
                f"**Error Type:** {error_type}\n"
                f"**Details:** {error_details[:200]}...\n\n"
                "💡 **Possible Causes:**\n"
                "• Network connectivity issues\n"
                "• Image format not supported\n"
                "• Database connection problems\n"
                "• Temporary server issues\n\n"
                "💡 **Please Try:**\n"
                "1. Check your internet connection\n"
                "2. Take a new clear screenshot\n"
                "3. Try sending it again in 1-2 minutes\n"
                "4. Contact support if the issue persists\n\n"
                "We apologize for the inconvenience!"
            )
    
    async def _get_pending_payments(self, user_id: str) -> List[Dict[str, Any]]:
        """Get pending payment requests for user."""
        try:
            # First try to get payments by user_id
            result = self.supabase_client.client.table("payment_requests").select("*").eq(
                "user_id", user_id
            ).eq("status", "pending").order("created_at", desc=True).execute()
            
            if result.data:
                return result.data
            
            # If no payments found for this user_id, check if there are any pending payments for this phone
            # This handles cases where registration creates a new user_id but payment was initiated with temp user_id
            logger.info(f"No pending payments found for user_id {user_id}, checking for any pending payments")
            
            # Get all pending payments (last 24 hours) and return them for auto-approval
            yesterday = (datetime.now() - timedelta(hours=24)).strftime('%Y-%m-%d %H:%M:%S')
            
            result = self.supabase_client.client.table("payment_requests").select("*").eq(
                "status", "pending"
            ).gte("created_at", yesterday).order("created_at", desc=True).limit(5).execute()
            
            return result.data or []
            
        except Exception as e:
            logger.error(f"Error getting pending payments: {e}")
            return []
    
    async def _store_payment_screenshot(self, payment_id: str, image_data: bytes) -> str:
        """Store payment screenshot in Supabase storage."""
        try:
            # Upload to storage
            file_path = f"payment_screenshots/{payment_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
            
            screenshot_url = await self.supabase_client.upload_file(
                bucket="payment-proofs",
                file_path=file_path,
                file_data=image_data,
                content_type="image/jpeg"
            )
            
            # Update payment request with screenshot URL
            self.supabase_client.client.table("payment_requests").update({
                "screenshot_url": screenshot_url,
                "screenshot_uploaded_at": datetime.now().isoformat()
            }).eq("id", payment_id).execute()
            
            logger.info(f"Stored payment screenshot for payment {payment_id}")
            return screenshot_url
            
        except Exception as e:
            logger.error(f"Error storing payment screenshot: {e}")
            raise
    
    async def _approve_payment(self, payment_id: str, user_id: str, amount: float) -> bool:
        """Approve payment and credit user wallet."""
        try:
            # Update payment status
            self.supabase_client.client.table("payment_requests").update({
                "status": "approved"
            }).eq("id", payment_id).execute()
            
            # Get current balance
            current_balance = await self.supabase_client.get_user_balance(user_id)
            
            # Credit wallet
            new_balance = current_balance + amount
            await self.supabase_client.update_user_balance(user_id, new_balance)
            
            # Record transaction
            await self.supabase_client.record_transaction(
                user_id=user_id,
                amount=amount,
                transaction_type="deposit",
                description=f"UPI payment credit - Payment ID: {payment_id}"
            )
            
            logger.info(f"Approved payment {payment_id} for user {user_id}, credited ₹{amount}")
            return True
            
        except Exception as e:
            logger.error(f"Error approving payment: {e}")
            return False
    
    def is_waiting_for_payment_screenshot(self, phone_number: str) -> bool:
        """Check if user is waiting to send payment screenshot."""
        return phone_number in self.payment_screenshot_state
    
    def get_payment_screenshot_info(self, phone_number: str) -> Optional[Dict[str, Any]]:
        """Get payment screenshot waiting info for user."""
        return self.payment_screenshot_state.get(phone_number)
    
    def clear_payment_screenshot_state(self, phone_number: str):
        """Clear payment screenshot waiting state for user."""
        if phone_number in self.payment_screenshot_state:
            del self.payment_screenshot_state[phone_number]
    
    def is_in_fund_conversation(self, phone_number: str) -> bool:
        """Check if user is currently in a fund conversation flow."""
        return phone_number in self.fund_state
        
    async def handle_fund_conversation(self, user_id: str, phone_number: str, message: str) -> str:
        """Handle ongoing fund conversation - alias for handle_add_funds."""
        return await self.handle_add_funds(user_id, phone_number, message) 