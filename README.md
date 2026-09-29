# CatalogIQ

CatalogIQ is an asynchronous, resilient product enrichment service that converts unorganized seller listings into clean, structured, and searchable catalogue items. Built with Python (FastAPI + AsyncIO) and vanilla JavaScript, it handles high-throughput background processing, concurrency control, single-flight deduplication, and retries with exponential backoff.

---

## 1. Setup Steps (Clean Machine Setup)

### Prerequisites
* Python 3.10 or higher
* Git

### Installation
```bash
# 1. Clone the repository
git clone <your-repository-url>
cd CatalogIQ

# 2. Create and activate a Python virtual environment
python -m venv venv

# On Linux/macOS:
source venv/bin/activate

# On Windows (PowerShell):
.\venv\Scripts\Activate.ps1

# On Windows (Command Prompt):
.\venv\Scripts\activate.bat

# 3. Install dependencies
pip install -r requirements.txt