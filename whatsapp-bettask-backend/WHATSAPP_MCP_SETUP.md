 # WhatsApp MCP Integration Setup Guide

This guide shows how to set up **WhatsApp MCP** integration with your BetTask backend instead of using WhatsApp Business API webhooks.

## 🏗️ **Architecture Overview**

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   WhatsApp      │◄──►│  WhatsApp MCP    │◄──►│   BetTask       │
│   (Your Phone)  │    │  Bridge (Go)     │    │   Backend       │
│                 │    │  Port: 8080      │    │   (Python)      │
└─────────────────┘    └──────────────────┘    │   Port: 8000    │
                              │                 └─────────────────┘
                              ▼                          │
                       ┌──────────────┐                  │
                       │   SQLite     │                  ▼
                       │   Message    │         ┌─────────────────┐
                       │   Database   │         │   Supabase      │
                       └──────────────┘         │   Database      │
                                               └─────────────────┘
```

## 🔧 **What Changed**

### ❌ **Removed (Webhook-based)**
- `WHATSAPP_WEBHOOK_SECRET` - Not needed for MCP
- `WHATSAPP_VERIFY_TOKEN` - Not needed for MCP  
- `/webhook/whatsapp` endpoints
- Webhook signature verification
- External webhook URL setup

### ✅ **Added (MCP-based)**
- Direct SQLite database access to WhatsApp messages
- REST API client for sending messages via MCP bridge
- Background polling for new messages
- Local media file download and processing
- Direct integration with WhatsApp Web API

## 🚀 **Setup Instructions**

### **Step 1: Start WhatsApp MCP Bridge**

1. **Navigate to WhatsApp MCP directory:**
   ```bash
   cd /Users/dev16/Documents/Test\ project/dare-you-succeed\ 3/whatsapp-mcp/whatsapp-bridge
   ```

2. **Install Go dependencies:**
   ```bash
   go mod tidy
   ```

3. **Start the bridge:**
   ```bash
   go run main.go
   ```

4. **Scan QR Code:**
   - A QR code will appear in your terminal
   - Open WhatsApp on your phone
   - Go to Settings > Linked Devices > Link a Device
   - Scan the QR code
   - The bridge will connect and start syncing messages

### **Step 2: Configure Your Backend**

1. **Update your `.env` file:**
   ```bash
   # Copy the example configuration
   cp env_example_mcp.txt .env
   ```

2. **Edit `.env` with your credentials:**
   ```env
   # Supabase Configuration
   SUPABASE_URL=https://your-project.supabase.co
   SUPABASE_ANON_KEY=your_anon_key
   SUPABASE_SERVICE_ROLE_KEY=your_service_role_key

   # WhatsApp MCP Configuration  
   WHATSAPP_MCP_BRIDGE_URL=http://localhost:8080
   WHATSAPP_MCP_DATABASE_PATH=/Users/dev16/Documents/Test project/dare-you-succeed 3/whatsapp-mcp/whatsapp-bridge/store/messages.db

   # Gemini AI Configuration
   GEMINI_API_KEY=your_gemini_api_key
   ```

3. **Remove old webhook variables:**
   - Delete `WHATSAPP_WEBHOOK_SECRET` if present
   - Delete `WHATSAPP_VERIFY_TOKEN` if present

### **Step 3: Start Your Backend**

```bash
cd whatsapp-bettask-backend
python main.py
```

## 🔍 **How It Works**

### **Message Flow**

1. **Incoming Messages:**
   - User sends WhatsApp message to your phone
   - WhatsApp MCP bridge receives message via WhatsApp Web API
   - Message is stored in local SQLite database
   - Your backend polls the database every 10 seconds
   - New messages are processed and routed to appropriate handlers
   - Responses are sent back via MCP bridge

2. **Outgoing Messages:**
   - Your backend calls `whatsapp_mcp.send_message()`
   - Request is sent to MCP bridge REST API (`localhost:8080/api/send`)
   - Bridge sends message via WhatsApp Web API
   - Message appears in user's WhatsApp

### **Media Handling**

1. **Media Reception:**
   - Bridge stores media metadata in SQLite
   - Your backend detects media messages
   - Downloads media using `whatsapp_mcp.download_media()`
   - Media files are saved locally for processing

2. **Media Sending:**
   - Your backend specifies `media_path` in send request
   - Bridge uploads media to WhatsApp servers
   - Sends media message with optional caption

## 🛠️ **API Endpoints**

### **Health Check**
```bash
GET http://localhost:8000/health
```
Response shows status of all services:
```json
{
  "status": "healthy",
  "services": {
    "supabase": "healthy",
    "whatsapp_mcp": "healthy", 
    "gemini": "configured"
  }
}
```

### **Send Message (Testing)**
```bash
POST http://localhost:8000/api/send-message
Content-Type: application/json

{
  "phone_number": "+1234567890",
  "message": "Hello from BetTask!"
}
```

### **Get Recent Messages**
```bash
GET http://localhost:8000/api/recent-messages?phone_number=+1234567890&hours=24
```

## 🐛 **Troubleshooting**

### **WhatsApp MCP Bridge Issues**

1. **QR Code Not Showing:**
   ```bash
   cd whatsapp-mcp/whatsapp-bridge
   rm -rf store/whatsapp.db  # Remove old session
   go run main.go
   ```

2. **Bridge Not Responding:**
   ```bash
   curl http://localhost:8080/
   # Should return empty response with 200 status
   ```

3. **Message Database Missing:**
   - Check path: `/Users/dev16/Documents/Test project/dare-you-succeed 3/whatsapp-mcp/whatsapp-bridge/store/messages.db`
   - Bridge creates this automatically after connecting

### **Backend Issues**

1. **Connection Failed:**
   ```bash
   curl http://localhost:8000/health
   ```
   Check which services are failing.

2. **No Messages Processing:**
   - Verify bridge is running on port 8080
   - Check database path in `.env` 
   - Ensure user profiles exist in Supabase

3. **Import Errors:**
   ```bash
   python test_basic.py
   ```
   This will show which dependencies are missing.

## 📊 **Message Processing Flow**

```python
# 1. Backend polls for new messages every 10 seconds
users = await supabase_client.get_active_users()

# 2. Check each user for new messages  
new_messages = whatsapp_mcp.get_unread_messages(phone_number, last_check)

# 3. Process each message
for message in new_messages:
    # Route to appropriate handler (challenge, help, etc.)
    response = await intent_router.route_message(...)
    
    # Send response back via MCP
    await whatsapp_mcp.send_message(phone_number, response)
```

## 🎯 **Key Benefits of MCP vs Webhooks**

| Feature | Webhooks | MCP |
|---------|----------|-----|
| **Setup Complexity** | High (ngrok, certificates) | Low (local only) |
| **External Dependencies** | Yes (webhook URL) | No |
| **Message History** | Limited | Full access |
| **Media Handling** | Complex | Built-in |
| **Development** | Need public URL | Local development |
| **Reliability** | Network dependent | Direct database |

## 🔐 **Security Considerations**

1. **Local Only:** MCP bridge runs locally, no external exposure required
2. **No Webhooks:** No need to expose your backend to the internet
3. **Direct Database:** Full control over message data
4. **WhatsApp Auth:** Uses official WhatsApp Web protocol

## 📝 **Next Steps**

1. **Test Message Flow:**
   - Send a WhatsApp message to your linked phone
   - Check logs to see message processing
   - Verify response is sent back

2. **Add Your Phone Number:**
   ```sql
   INSERT INTO user_profiles (phone_number, full_name) 
   VALUES ('+1234567890', 'Your Name');
   ```

3. **Create Your First Challenge:**
   - Send "create challenge" to your WhatsApp
   - Follow the bot prompts

4. **Production Deployment:**
   - Set up process managers (PM2, systemd) 
   - Configure proper logging
   - Set up database backups

---

🎉 **Your WhatsApp MCP integration is now ready!** Send a message to your phone to test it out.