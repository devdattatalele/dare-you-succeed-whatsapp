# Dare You Succeed - WhatsApp Integration

WhatsApp-based accountability system for goal achievement with financial stakes.

## Overview

This repository contains the WhatsApp components of the Dare You Succeed accountability app:

- **WhatsApp Backend** (`whatsapp-bettask-backend/`) - Python FastAPI backend that handles WhatsApp message processing
- **WhatsApp MCP** (`whatsapp-mcp/`) - WhatsApp MCP bridge for message handling

## Features

### 🎯 Challenge Creation
- Create accountability challenges via WhatsApp
- Set financial stakes (bet amounts)
- One-time or recurring challenges
- Natural language processing for goal setting

### 💰 Wallet Management
- Add funds via UPI payments
- Check wallet balance
- Transaction history
- Automatic stake deduction

### 📱 WhatsApp Integration
- Complete challenge management via WhatsApp
- Payment verification through screenshots
- Real-time message processing
- User registration and authentication

### 🤖 AI-Powered Features
- Intent classification using Gemini AI
- Payment verification through image analysis
- Natural language understanding

## Architecture

```
WhatsApp Messages → MCP Bridge → FastAPI Backend → Supabase Database
                                      ↓
                               Gemini AI Processing
```

## Quick Start

### 1. WhatsApp Backend Setup

```bash
cd whatsapp-bettask-backend
pip install -r requirements.txt
cp .env.example .env
# Configure environment variables
python main.py
```

### 2. WhatsApp MCP Setup

```bash
cd whatsapp-mcp
npm install
# Configure WhatsApp credentials
npm start
```

## Environment Variables

### Backend (.env)
```
SUPABASE_URL=your_supabase_url
SUPABASE_SERVICE_ROLE_KEY=your_service_key
GEMINI_API_KEY=your_gemini_key
```

### MCP Bridge
```
WHATSAPP_SESSION_ID=your_session
WEBHOOK_URL=http://localhost:8000/webhook
```

## Core Components

### Intent Router
Handles message classification and routing:
- Challenge creation flow
- Payment processing
- Balance inquiries
- Help and information

### Payment Handler
Manages financial transactions:
- UPI payment verification
- Balance updates
- Transaction recording

### Challenge Handler
Manages accountability challenges:
- Challenge creation and modification
- Deadline tracking
- Status updates

## API Endpoints

- `POST /webhook` - WhatsApp webhook for incoming messages
- `GET /health` - Health check endpoint
- `GET /` - Service status

## Database Schema

Uses Supabase with tables:
- `profiles` - User accounts
- `challenges` - Accountability challenges
- `wallets` - User balances
- `transactions` - Financial records

## Recent Fixes

✅ **Challenge Creation Flow Fixed** (June 2, 2025)
- "create challenge" now properly asks for goal instead of treating command as goal
- Improved intent classification
- Better conversation state handling

✅ **Authentication System Fixed** 
- Custom password-based auth replacing broken Supabase Auth triggers
- WhatsApp-specific user creation flow
- Payment verification fixes

## Usage Examples

### Create Challenge
```
User: "create challenge"
Bot: "🎯 What would you like to bet on?"
User: "go to gym today"
Bot: "💰 How much do you want to bet?"
User: "100"
Bot: "📋 Challenge Summary: ... Reply 'yes' to create"
```

### Check Balance
```
User: "balance"
Bot: "💰 Balance: ₹150.00"
```

### Add Funds
```
User: "add funds"
Bot: "💳 How much would you like to add?"
User: "500"
Bot: "📱 Please send UPI payment screenshot"
```

## Development

### Testing
```bash
# Test challenge creation
python test_challenge_creation_fix.py

# Test authentication
python test_new_auth_system.py

# Check user profiles
python check_profiles.py
```

### Logging
Comprehensive logging with different levels:
- INFO: General operations
- ERROR: Error conditions
- DEBUG: Detailed debugging

## Deployment

### Backend
- FastAPI application
- Can be deployed on any Python hosting service
- Requires PostgreSQL database (Supabase)

### MCP Bridge
- Node.js application
- Requires WhatsApp Business API access
- Can be deployed on VPS or cloud service

## Contributing

1. Fork the repository
2. Create feature branch
3. Test thoroughly
4. Submit pull request

## Security

- Environment variables for sensitive data
- Input validation and sanitization
- Rate limiting on API endpoints
- Secure webhook verification

## Support

For issues and questions:
- Check logs in respective components
- Review environment variable configuration
- Ensure database connectivity
- Verify WhatsApp MCP bridge status

---

**Status**: ✅ Active Development
**Last Updated**: June 2, 2025
**Version**: 1.0.0 