# Setup Guide

## Prerequisites

- Python 3.10 or higher
- pip (Python package installer)
- Virtual environment support
- OpenAI API key (minimum $5 credit)
- Anthropic API key (optional but recommended)

## Installation Steps

### 1. Extract the Project

```bash
# Extract the zip file
unzip compliance_validator_project.zip
cd compliance_validator_project
```

### 2. Create Virtual Environment

**macOS/Linux:**
```bash
python3 -m venv venv
source venv/bin/activate
```

**Windows:**
```bash
python -m venv venv
venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

This will install:
- OpenAI and Anthropic SDKs
- LangChain and LangChain Community
- Pydantic for data validation
- Pandas for data processing
- pytest for testing
- And more...

### 4. Configure API Keys

```bash
# Copy the example environment file
cp .env.example .env
```

Edit `.env` and add your API keys:
```bash
OPENAI_API_KEY=sk-proj-YOUR-KEY-HERE
ANTHROPIC_API_KEY=sk-ant-YOUR-KEY-HERE  # Optional
```

**Getting API Keys:**

**OpenAI:**
1. Go to https://platform.openai.com/api-keys
2. Sign up or log in
3. Create new secret key
4. Add minimum $5 credit at https://platform.openai.com/account/billing

**Anthropic (Optional but Recommended):**
1. Go to https://console.anthropic.com/
2. Sign up or log in
3. Get API key from settings
4. They offer $5 free credit for new users

### 5. Verify Installation

```bash
# Test that everything works
python test_first_invoice.py
```

You should see:
```
🚀 Compliance Validator - Quick Start Test

📄 Loading test invoice...
✓ Loaded: INV-2024-0001 - STANDARD_VALID

✅ VALIDATION PASSED - All checks successful!
```

### 6. Run Tests (Optional)

```bash
# Run unit tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=validators --cov-report=html
```

## Project Structure Verification

After setup, your project should look like:

```
compliance_validator_project/
├── venv/                  # ✓ Virtual environment created
├── .env                   # ✓ API keys configured
├── data/                  # ✓ Contains 7 data files
├── docs/                  # ✓ Contains 7 documentation files
├── models/                # ✓ Data models
├── validators/            # ✓ Validator implementations
├── utils/                 # ✓ Utility functions
├── tests/                 # ✓ Test suite
└── README.md             # ✓ Main documentation
```

## Troubleshooting

### Issue: "pip: command not found"

**Solution:**
```bash
# Try pip3 instead
pip3 install -r requirements.txt
```

### Issue: "python: command not found"

**Solution:**
```bash
# Try python3 instead
python3 test_first_invoice.py
```

### Issue: "No module named 'pydantic'"

**Solution:**
```bash
# Make sure virtual environment is activated
source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -r requirements.txt
```

### Issue: "API key not found"

**Solution:**
```bash
# Check that .env file exists
ls -la .env

# Check that keys are in the file
cat .env

# Make sure no extra spaces or quotes
# Should be: OPENAI_API_KEY=sk-proj-...
# Not: OPENAI_API_KEY="sk-proj-..."
```

### Issue: "Rate limit exceeded"

**Solution:**
- You may need to add credits to your OpenAI account
- Go to https://platform.openai.com/account/billing
- Add payment method and credits

### Issue: "Data file not found"

**Solution:**
```bash
# Make sure you're in the project root
pwd  # Should end with /compliance_validator_project

# Check data files exist
ls -la data/
# Should show: test_invoices.json, vendor_registry.json, etc.
```

## Next Steps

Once setup is complete:

1. **Read the README.md** - Overview of the project
2. **Read docs/quick_start_guide.md** - 30-minute tutorial
3. **Run test_first_invoice.py** - Verify everything works
4. **Explore the test data** - data/test_invoices.json
5. **Start building** - Add more validators

## Getting Help

1. Check **README.md** for complete documentation
2. Read **docs/** folder for detailed guides
3. Look at **example** implementations in docs/
4. Review **test data** to understand requirements

## Success Indicators

✅ Virtual environment activated
✅ All dependencies installed
✅ API keys configured
✅ test_first_invoice.py runs successfully
✅ Tests pass with pytest

**You're ready to build! 🚀**
