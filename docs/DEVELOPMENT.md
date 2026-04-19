# Development Guide

## 🛠️ Development Environment Setup

### IDE Configuration

#### IntelliJ IDEA
1. Import the project as a Maven project
2. Ensure Java 21 SDK is configured
3. Install Python plugin for AI service development
4. Configure remote interpreter for Python virtual environment

#### VS Code
1. Open the project folder
2. Install Java Extension Pack
3. Install Python extension
4. Configure Java home and Python interpreter

### Environment Variables

Create `.env` files for different environments:

**`.env.development`**
```env
APP_ENV=development
LOG_LEVEL=DEBUG
APP.ai.service.enabled=true
```

**`.env.production`**
```env
APP_ENV=production
LOG_LEVEL=INFO
APP.ai.service.enabled=true
```

## 🔧 Build and Test

### Maven Commands

```bash
# Clean build
mvn clean package

# Compile only
mvn compile

# Run tests
mvn test

# Run specific test class
mvn test -Dtest=ContractServiceTest

# Run with coverage
mvn test -DskipTests=false
```

### Python Testing

```bash
# Run all tests
pytest tests/

# Run specific test file
pytest tests/test_api.py

# Run with verbose output
pytest -v tests/

# Run with coverage
pytest --cov=app tests/
```

## 📊 Code Structure

### Backend (Java)

```
backend/
├── src/
│   ├── main/
│   │   ├── java/com/grim/backend/
│   │   │   ├── config/          # Configuration classes
│   │   │   ├── controller/      # REST controllers
│   │   │   ├── service/         # Business services
│   │   │   ├── model/           # JPA entities
│   │   │   ├── repository/      # MongoDB repositories
│   │   │   ├── exception/       # Custom exceptions
│   │   │   └── BackendApplication.java
│   │   └── resources/
│   │       ├── application.yaml # Main config
│   │       └── templates/       # Thymeleaf templates
│   └── test/
│       └── java/com/grim/backend/
```

### Frontend (Thymeleaf)

```
backend/src/main/resources/templates/
├── dashboard.html       # Main dashboard
├── upload.html          # Upload form
├── contract-detail.html # Contract details
├── analysis-result.html # Analysis results
└── error.html          # Error pages
```

### AI Service (Python)

```
ai-service/
├── app/
│   ├── __init__.py
│   ├── main.py          # FastAPI application
│   ├── config.py        # Configuration
│   ├── core/            # Core services
│   │   ├── embedder.py
│   │   ├── vector_store.py
│   │   ├── ollama_client.py
│   │   └── rag_pipeline.py
│   ├── api/
│   │   ├── routes.py    # API endpoints
│   │   └── __init__.py
│   └── models/
│       ├── schemas.py   # Pydantic models
│       └── __init__.py
├── tests/
│   ├── test_api.py
│   └── test_chunking.py
└── .env                 # Environment variables
```

## 🚀 Running the Application

### Development Mode

**Backend:**
```bash
cd backend
mvn spring-boot:run
```

**AI Service:**
```bash
cd ai-service
uvicorn main:app --host 0.0.0.0 --port 5000 --reload
```

The `--reload` flag enables auto-reload on code changes.

### Production Mode

**Backend:**
```bash
cd backend
java -jar target/ai-contract-system-1.0.0.jar
```

**AI Service:**
```bash
cd ai-service
uvicorn main:app --host 0.0.0.0 --port 5000
```

### Docker Compose

```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

## 🐛 Debugging

### Backend Debugging

**IntelliJ IDEA:**
1. Open the project
2. Click on the run/debug configuration
3. Set breakpoints
4. Click the debug icon (🐛)

**VS Code:**
1. Open the project
2. Go to Run and Debug
3. Create a new Java configuration
4. Set breakpoints and start debugging

### AI Service Debugging

**Python Debugging:**
```bash
# Using pdb
python -m pdb main.py

# Using VS Code debugger
# Set breakpoints and use the debug console

# Using logging
import logging
logging.basicConfig(level=logging.DEBUG)
```

**FastAPI Debug Mode:**
```bash
uvicorn main:app --host 0.0.0.0 --port 5000 --reload --log-level debug
```

### Common Issues

**Issue: MongoDB Connection Failed**
```bash
# Check if MongoDB is running
docker ps | grep mongo

# Start MongoDB
docker-compose up -d database
```

**Issue: Ollama Model Not Found**
```bash
# Check available models
ollama list

# Download model if missing
ollama pull gemma3:4b
```

**Issue: Port Already in Use**
```bash
# Find process using port
lsof -ti:6969 | xargs kill -9

# Or use different port
sed -i 's/port: 6969/port: 6970/' backend/src/main/resources/application.yaml
```

## 📈 Performance Optimization

### JVM Tuning

```bash
# Set JVM options
export JAVA_OPTS="-Xms512m -Xmx2g -XX:+UseG1GC"
mvn spring-boot:run $JAVA_OPTS
```

### Python Performance

```python
# Use batch processing
embedder.encode(batch_of_texts)  # Instead of individual encodes

# Enable parallel processing
from concurrent.futures import ThreadPoolExecutor
```

### Database Optimization

```yaml
# application.yaml
spring:
  data:
    mongodb:
      options:
        connections-per-host: 10
        threads-allowed-to-block-for-connection-multiplier: 5
```

## 🔄 Version Control

### Git Workflow

```bash
# Create feature branch
git checkout -b feature/contract-analysis

# Stage changes
git add backend/src/main/java/com/grim/backend/service/ContractService.java

# Commit with message
git commit -m "feat: add contract analysis service"

# Push to remote
git push origin feature/contract-analysis
```

### Code Review Checklist

- [ ] Code follows project conventions
- [ ] Tests are included for new features
- [ ] Documentation is updated
- [ ] No sensitive information in commits
- [ ] Performance impact considered
- [ ] Error handling implemented

## 📝 Best Practices

### Java Development
1. Use Lombok annotations to reduce boilerplate
2. Follow Spring Boot conventions
3. Implement proper exception handling
4. Use repository pattern for data access
5. Add comprehensive logging

### Python Development
1. Use Pydantic for data validation
2. Implement proper error handling
3. Use async/await for I/O operations
4. Add type hints
5. Write comprehensive tests

### API Design
1. Use consistent naming conventions
2. Implement proper error responses
3. Add comprehensive documentation
4. Use appropriate HTTP status codes
5. Implement rate limiting

## 🚦 Continuous Integration

### GitHub Actions

```yaml
name: CI Pipeline
on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main ]

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Set up JDK 21
        uses: actions/setup-java@v2
      - name: Build with Maven
        run: mvn clean package
      - name: Run tests
        run: mvn test
```

## 📊 Monitoring

### Application Logs

```bash
# View application logs
docker-compose logs backend

# Follow logs in real-time
docker-compose logs -f backend

# Search specific logs
docker-compose logs | grep ERROR
```

### Health Checks

```bash
# Backend health
curl http://localhost:6969/api/ai/health

# Database connectivity
curl http://localhost:6969/api/health/db

# AI service connectivity
curl http://localhost:6969/api/health/ai
```

## 🎯 Development Tips

1. **Start Small**: Begin with small features and tests
2. **Test Early**: Write tests before implementing features
3. **Document**: Keep documentation up to date
4. **Code Review**: Review code regularly
5. **Refactor**: Improve code quality continuously
6. **Monitor**: Track application performance
7. **Backup**: Regular database backups
8. **Version**: Tag releases properly

## 📚 Learning Resources

- [Spring Boot Documentation](https://docs.spring.io/spring-boot/docs/current/reference/html/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [MongoDB Documentation](https://docs.mongodb.com/)
- [FAISS Documentation](https://github.com/facebookresearch/faiss)
- [Ollama Documentation](https://ollama.ai/)