 # Crypto News Scraper

This project is a Python application that scrapes cryptocurrency news from various sources, analyzes the articles for market impact, and stores the results in a SQLite database.

## Requirements

To run this project, you need to have Python 3.x installed on your machine. You can check your Python version by running:


## Installation

1. **Clone the repository** (if applicable):
   ```bash
   git clone <repository-url>
   cd <repository-directory>
   ```

2. **Create a virtual environment** (optional but recommended):
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows use `venv\Scripts\activate`
   ```

3. **Install the required packages**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Run the application**:
   ```bash
   python news-ai.py
   ```

5. **Access the API**: The application will run on `http://127.0.0.1:8000`. You can access the following endpoints:
   - `/crypto/start`: Start the scraping process.
   - `/crypto/status`: Get the current scraping status.
   - `/crypto/summary`: Get analyzed articles from the database.
   - `/crypto/<coin>`: Get 7-day statistics for a specific coin from analyzed articles.

