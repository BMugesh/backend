# ArogyaMitra Backend

🏥 **AI-Powered Healthcare Assistant Backend**

A Flask-based backend service providing AI-driven healthcare guidance, hospital location services, appointment booking, and real-time health news for the ArogyaMitra platform.

## 🚀 Features

- **AI Health Assistant**: Powered by Google's Gemini AI
- **Hospital Location Service**: Find nearby healthcare facilities
- **Appointment Booking**: Schedule medical appointments
- **Multilingual Support**: English, Hindi, Gujarati, Bengali, Marathi, Tamil
- **Real-time Health News**: RSS feeds and NewsAPI integration
- **Voice Integration**: Compatible with Vapi voice AI
- **Caching System**: In-memory caching for performance
- **Security**: Rate limiting, CORS, and input validation

## 📋 Requirements

### System Requirements
- Python 3.9+ (recommended: 3.11.7)
- 2GB+ RAM
- Internet connection for AI services

### API Keys Required
- Google Gemini API Key
- NewsAPI Key (optional)
- Vapi API credentials (for voice features)

## 🔧 Installation

### Quick Start
```bash
# Clone repository
git clone https://github.com/arogyamitra/backend.git
cd backend

# Install dependencies
pip install -r requirements.txt

# Set up environment variables
cp .env.example .env
# Edit .env with your API keys

# Run the application
python backend.py
```

### Development Setup
```bash
# Install development dependencies
pip install -r requirements-dev.txt

# Run with auto-reload
flask --app backend.py --debug run

# Run tests
pytest

# Code formatting
black backend.py

# Linting
flake8 backend.py
```

### Production Deployment
```bash
# Install production dependencies
pip install -r requirements-prod.txt

# Run with Gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 backend:app

# Or use the included Procfile for Heroku
```

## 🌍 Environment Variables

Create a `.env` file with the following variables:

```env
# Required
GEMINI_API_KEY=your_gemini_api_key_here

# Optional
NEWS_API_KEY=your_news_api_key_here
FLASK_ENV=production
PORT=5000

# Database (if using)
DATABASE_URL=postgresql://user:pass@localhost/dbname

# Redis (for caching)
REDIS_URL=redis://localhost:6379/0
```

## 🔌 API Endpoints

### Health Assistant
- `POST /ask` - Submit health queries to AI
- `GET /health` - Health check endpoint

### Hospital Services  
- `POST /hospitals` - Find hospitals by condition/location
- `POST /health-centers` - Find nearby health centers
- `POST /bookings` - Create appointment bookings
- `GET /bookings/<id>` - Get booking details

### News Services
- `POST /news` - Get AI-generated health news
- `POST /news-realtime` - Get real-time RSS health news

## 📊 API Usage Examples

### Health Query
```bash
curl -X POST http://localhost:5000/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "I have fever and headache for 2 days"}'
```

### Find Hospitals
```bash
curl -X POST http://localhost:5000/hospitals \
  -H "Content-Type: application/json" \
  -d '{"condition": "heart", "location": "Mumbai"}'
```

### Health Centers
```bash
curl -X POST http://localhost:5000/health-centers \
  -H "Content-Type: application/json" \
  -d '{"latitude": 19.0760, "longitude": 72.8777}'
```

## 🏗️ Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Frontend      │────│   Flask API      │────│   Gemini AI     │
│   (Next.js)     │    │   (Python)       │    │   (Google)      │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                │
                       ┌────────┴────────┐
                       │                 │
                  ┌────▼────┐    ┌──────▼──────┐
                  │  Cache  │    │  External   │
                  │(Memory) │    │  APIs       │
                  └─────────┘    └─────────────┘
```

## 🧪 Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=backend

# Run specific test file
pytest tests/test_api.py

# Run with verbose output
pytest -v
```

## 🚀 Deployment

### Heroku
```bash
# Create Heroku app
heroku create arogyamitra-backend

# Set environment variables
heroku config:set GEMINI_API_KEY=your_key_here

# Deploy
git push heroku main
```

### Docker
```bash
# Build image
docker build -t arogyamitra-backend .

# Run container
docker run -p 5000:5000 --env-file .env arogyamitra-backend
```

### Railway/Render
- Use `requirements.txt` for dependencies
- Set environment variables in dashboard
- Deploy from GitHub repository

## 🔒 Security Features

- **Rate Limiting**: Prevents API abuse
- **CORS Configuration**: Secure cross-origin requests
- **Input Validation**: Sanitizes user inputs
- **Error Handling**: Secure error responses
- **API Key Management**: Environment-based configuration

## 📈 Performance Optimizations

- **In-memory Caching**: Reduces API calls
- **Connection Pooling**: Efficient HTTP requests
- **Async Support**: Non-blocking operations
- **Response Compression**: Faster data transfer
- **Database Indexing**: Optimized queries

## 🛠️ Development Tools

### Code Quality
- **Black**: Code formatting
- **Flake8**: Linting
- **MyPy**: Type checking
- **Bandit**: Security analysis
- **Safety**: Dependency vulnerability scanning

### Testing
- **Pytest**: Test framework
- **Coverage**: Code coverage analysis
- **Factory Boy**: Test data generation
- **Pytest-Flask**: Flask testing utilities

## 📚 Documentation

- **API Documentation**: Available at `/docs` endpoint
- **Swagger UI**: Interactive API explorer
- **Code Documentation**: Inline docstrings
- **Architecture Diagrams**: In `/docs` folder

## 🤝 Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open Pull Request

### Development Guidelines
- Follow PEP 8 style guide
- Write tests for new features
- Update documentation
- Use meaningful commit messages

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🆘 Support

- **Documentation**: [docs.arogyamitra.com](https://docs.arogyamitra.com)
- **Issues**: [GitHub Issues](https://github.com/arogyamitra/backend/issues)
- **Email**: support@arogyamitra.com
- **Discord**: [ArogyaMitra Community](https://discord.gg/arogyamitra)

## 🙏 Acknowledgments

- Google Gemini AI for healthcare insights
- OpenStreetMap for location services
- Indian healthcare organizations for guidance
- Open source community for libraries

---

**Built with ❤️ for healthcare accessibility in India**
