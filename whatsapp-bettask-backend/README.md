# WhatsApp BetTask Backend

A complete WhatsApp-driven self-accountability betting system powered by AI. Users can create challenges, set financial stakes, submit proof via WhatsApp, and get AI-powered verification.

## 🚀 Features

- **WhatsApp Integration**: Complete message handling via WhatsApp MCP
- **AI-Powered**: Gemini AI for intent classification and image verification  
- **Challenge Management**: Create, track, and verify completion of personal challenges
- **Financial Stakes**: Real money betting system with Supabase wallet management
- **Smart Reminders**: Automated notifications before deadlines
- **Natural Language**: Parse dates, amounts, and goals from conversational input
- **Proof Verification**: AI analysis of photos/videos for challenge completion

## 🏗️ Architecture

```
whatsapp-bettask-backend/
├── main.py                 # FastAPI application entry point
├── config/
│   └── settings.py         # Configuration management
├── api/
│   └── webhook.py          # WhatsApp MCP integration
├── services/
│   └── supabase_client.py  # Database operations
├── ai/
│   ├── gemini_client.py    # AI integration
│   └── prompts.py          # AI prompts library
├── handlers/
│   ├── intent_router.py    # Message routing
│   ├── challenge_handler.py # Challenge operations
│   ├── proof_handler.py    # Proof verification
│   ├── balance_handler.py  # Wallet management
│   ├── reminder_handler.py # Reminder system
│   └── help_handler.py     # User assistance
├── utils/
│   ├── logger.py           # Logging utilities
│   ├── retry.py            # Retry logic
│   ├── date_parser.py      # Natural date parsing
│   └── error_handler.py    # Error management
└── cron/
    └── reminder_job.py     # Automated reminders
```

## 🔧 Setup Instructions

### 1. Install Dependencies

```bash
cd whatsapp-bettask-backend
pip install -r requirements.txt
```

### 2. Configure Environment

Copy the example environment file:
```bash
cp env.example .env
```

Edit `.env` with your configuration:

```env
# Required: Supabase Configuration
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=your_anon_key_here
SUPABASE_SERVICE_ROLE_KEY=your_service_role_key_here

# Required: Gemini AI
GEMINI_API_KEY=your_gemini_api_key_here

# Optional: WhatsApp MCP (for production)
WHATSAPP_MCP_URL=http://localhost:3000
WHATSAPP_WEBHOOK_SECRET=your_webhook_secret
```

### 3. Set Up Database

Run the SQL commands from `../DATABASE_SETUP.md` in your Supabase dashboard to create the required tables and policies.

### 4. Run the Application

```bash
python main.py
```

The server will start on `http://localhost:8000`

## 📱 User Flow Example

1. **User**: "I want to go to the gym tomorrow, bet ₹200"
2. **AI**: Classifies intent → creates challenge → deducts ₹200
3. **System**: Sends confirmation and sets up automatic reminder
4. **Next day**: Automated reminder sent via WhatsApp
5. **User**: Sends gym selfie
6. **AI**: Verifies image → approves/rejects → handles payout

## 🔌 API Endpoints

### Core Endpoints

- `POST /webhook/whatsapp` - WhatsApp message webhook
- `GET /webhook/whatsapp` - Webhook verification
- `GET /health` - Health check
- `POST /api/send-reminder` - Manual reminder trigger

### Message Types Supported

- **Text messages**: Challenge creation, proof submission, commands
- **Image/Video**: Automatic proof verification
- **Interactive**: Button responses and quick actions

## 🤖 AI Capabilities

### Intent Classification
Automatically understands user messages:
- Challenge creation requests
- Proof submissions  
- Balance inquiries
- Reminder requests
- Help requests

### Image Verification
Gemini Vision analyzes proof photos for:
- Authenticity and relevance
- Challenge completion evidence
- Context and effort demonstration
- Anti-cheating detection

### Natural Language Processing
- **Date parsing**: "tomorrow", "in 2 hours", "next Monday 3pm"
- **Amount extraction**: "₹200", "bet 150", "stake ₹500"
- **Goal enhancement**: AI improves vague goals into specific challenges

## 💾 Database Schema

### Core Tables
- `profiles` - User profiles with phone numbers and balances
- `challenges` - Challenge records with deadlines and amounts
- `task_submissions` - Proof submissions with verification status
- `transactions` - Financial transaction history
- `wallets` - User balance management
- `reminders` - Scheduled notification system

### Security
- Row-Level Security (RLS) enabled on all tables
- Phone-based user identification
- Secure file storage for proof images

## 🔔 Reminder System

### Automatic Reminders
- Set 2 hours before every challenge deadline
- Smart scheduling prevents past-time reminders
- Motivational messaging with stakes information

### Custom Reminders
Users can set additional reminders:
```
"Remind me in 1 hour"
"Set reminder for tomorrow 9am"
"Remind me 30 minutes before deadline"
```

### Cron Job
Run automated reminders:
```bash
python cron/reminder_job.py
```

## 🛡️ Error Handling

### Comprehensive Error Management
- Custom exception classes for different error types
- Graceful fallbacks when AI services are unavailable
- Retry logic with exponential backoff
- Detailed logging for debugging

### Error Types
- `ValidationError` - Input validation failures
- `InsufficientBalanceError` - Wallet issues
- `VerificationError` - Proof verification problems
- `AIServiceError` - AI API failures

## 🚦 Rate Limiting

### Built-in Protection
- API rate limiting (60 requests/minute default)
- WhatsApp message throttling
- Retry delays for external services
- Graceful degradation under load

## 🔍 Logging

### Structured Logging
- Request/response tracking
- WhatsApp message logging
- AI interaction monitoring
- Database operation timing
- Error context preservation

### Log Levels
- `DEBUG` - Detailed development info
- `INFO` - General operation flow
- `WARNING` - Recoverable issues
- `ERROR` - Error conditions
- `CRITICAL` - System failures

## 🧪 Testing

### Manual Testing
```bash
# Test reminder system
curl -X POST http://localhost:8000/api/send-reminder

# Health check
curl http://localhost:8000/health
```

### Development Mode
Set `DEBUG=true` in `.env` for:
- Detailed logging
- Auto-reload on code changes
- API documentation at `/docs`

## 🚀 Production Deployment

### Environment Variables
```env
DEBUG=false
LOG_LEVEL=INFO
ENVIRONMENT=production
```

### Process Management
```bash
# Using gunicorn
gunicorn main:app -w 4 -k uvicorn.workers.UvicornWorker

# Using PM2
pm2 start main.py --name bettask-backend
```

### Background Jobs
Set up cron job for automated reminders:
```bash
# Every 15 minutes
*/15 * * * * cd /path/to/backend && python cron/reminder_job.py
```

## 📊 Monitoring

### Health Checks
- Database connectivity
- AI service availability
- WhatsApp MCP status
- Memory and performance metrics

### Metrics Tracking
- Message processing times
- AI verification accuracy
- User engagement rates
- Challenge success rates

## 🔐 Security

### Data Protection
- Phone number masking in logs
- Secure webhook signature verification
- Environment variable isolation
- RLS database policies

### Best Practices
- Input validation and sanitization
- Rate limiting and abuse prevention
- Error message sanitization
- Secure file upload handling

## 🛠️ Troubleshooting

### Common Issues

**Import Error - pydantic_settings**
```bash
pip install pydantic-settings
```

**Database Connection Failed**
- Check Supabase URL and keys in `.env`
- Verify network connectivity
- Check Supabase dashboard for issues

**Gemini AI Errors**
- Verify API key in Google AI Studio
- Check API quotas and limits
- Ensure proper model permissions

**WhatsApp Messages Not Sending**
- Verify WhatsApp MCP is running
- Check webhook URL configuration
- Validate phone number formats

### Debug Mode
Enable detailed logging:
```env
DEBUG=true
LOG_LEVEL=DEBUG
```

## 📈 Performance

### Optimization Features
- Async/await throughout
- Connection pooling
- Intelligent caching
- Background task processing
- Efficient database queries

### Scalability
- Stateless architecture
- Horizontal scaling ready
- Database connection pooling
- External service retry logic

## 🤝 Contributing

### Development Setup
1. Fork the repository
2. Install dependencies: `pip install -r requirements.txt`
3. Set up environment variables
4. Run tests: `pytest`
5. Start development server: `python main.py`

### Code Style
- Follow PEP 8 guidelines
- Use type hints throughout
- Add docstrings to all functions
- Write comprehensive error handling

## 📞 Support

For issues and questions:
1. Check the troubleshooting section
2. Review logs for error details
3. Verify configuration settings
4. Test with minimal examples

## 🎯 Next Steps

The backend is production-ready! To get started:

1. **Set up your environment variables**
2. **Configure Supabase database**
3. **Get your Gemini API key**
4. **Run the server**
5. **Test with WhatsApp messages**

The system will handle the rest automatically! 🚀 