# Changelog

## Recent Updates (2025-12-04)

### Project Organization

#### Documentation
- **Moved all markdown docs to `docs/` folder**
  - SETUP_GUIDE.md
  - STATUS.md
  - MODEL_SELECTION_GUIDE.md
  - DOCKER_SETUP.md
  - RETRY_STRATEGY.md
  - KEYBOARD_SHORTCUTS.md
  - LOCAL_MODELS.md
  - QUICK_REFERENCE.md
- **Created TESTING.md** - Comprehensive guide for running tests
- **Created CHANGELOG.md** - This file

#### Tests
- **Moved all tests to `tests/` folder**
  - test_agent.py
  - test_force_model.py
- **Added testing documentation** - See docs/TESTING.md

#### Configuration
- **Organized requirements.txt**
  - Added clear sections for different dependency types
  - Added comments for optional dependencies
  - Included installation notes
  
- **Created .env.example**
  - Template for environment variables
  - Documentation for all API keys
  - Security best practices
  
- **Enhanced .gitignore**
  - Added comprehensive Python patterns
  - IDE support (VSCode, PyCharm, Vim, Emacs, Sublime)
  - OS-specific files (macOS, Windows, Linux)
  - Testing and coverage files
  - AI tool directories
  - Security patterns (keys, secrets)

### Feature Additions

#### Multi-Provider Support
- **Added 3 new LLM providers:**
  1. **Anthropic** (Claude models)
  2. **Google AI** (Gemini via AI Studio)
  3. **Groq** (fast inference)

- **New models available:**
  - claude-3-5-sonnet-20241022 (Anthropic)
  - claude-3-5-haiku-20241022 (Anthropic)
  - gemini-2.0-flash-exp (Google)
  - gemini-1.5-pro (Google)
  - llama-3.3-70b-versatile (Groq)
  - mixtral-8x7b-32768 (Groq)

#### Graceful Degradation
- **API key fallback system:**
  - If provider API key missing, tries OpenRouter as fallback
  - If no API keys available, falls back to local models
  - Clear warnings in logs about missing keys
  - Service continues to work with local models

- **Provider-specific clients:**
  - Native Anthropic client (langchain-anthropic)
  - Native Google client (langchain-google-genai)
  - Graceful fallback to OpenAI-compatible interface

#### Code Improvements
- **Refactored llm_system.py:**
  - New `_get_model_provider()` method
  - New `_setup_remote_model()` method
  - Cleaner provider handling
  - Better error messages

- **Updated config.py:**
  - Support for new providers (anthropic, google, groq)
  - API key mapping for all providers

- **Enhanced config.yaml:**
  - Provider field for each model
  - Base URLs for all providers
  - Clear model organization

### Files Modified

#### Core Files
- `.env` - Added new API key sections
- `.env.example` - Created comprehensive template
- `.gitignore` - Enhanced with best practices
- `requirements.txt` - Organized and documented
- `config/config.yaml` - Added new providers and models

#### Source Code
- `src/agent/llm_system.py` - Multi-provider support
- `src/utils/config.py` - New provider mappings

#### Documentation
- `docs/TESTING.md` - New file
- `docs/CHANGELOG.md` - This file

### Migration Notes

If updating from a previous version:

1. **Update dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Optional: Install provider packages:**
   ```bash
   # For Anthropic Claude
   pip install langchain-anthropic
   
   # For Google Gemini
   pip install langchain-google-genai
   ```

3. **Update .env file:**
   - Copy new sections from .env.example
   - Add API keys for new providers (optional)

4. **Test the service:**
   ```bash
   python3 run_service.py
   ```

### Breaking Changes

None. All changes are backward compatible.

### Known Issues

None reported.

### Next Steps

Potential future improvements:
- Add more model providers (Cohere, Together AI, etc.)
- Implement model performance tracking
- Add cost tracking per provider
- Create web dashboard for model management
