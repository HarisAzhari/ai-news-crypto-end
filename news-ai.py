from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from datetime import datetime, timedelta
import undetected_chromedriver as uc
from threading import Thread
from queue import Queue
import traceback
import google.generativeai as genai
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
import time
import requests
from bs4 import BeautifulSoup
import json
from flask import Flask, jsonify
from threading import Thread
from typing import Dict, List, Any

app = Flask(__name__)

def setup_undetected_driver():
    options = webdriver.ChromeOptions()
    options.add_argument("start-maximized")
    return uc.Chrome(options=options)

# Global variables for status tracking
scraping_status = {
    "is_running": False,
    "total_urls": 0,
    "processed_urls": 0,
    "current_url": "",
    "completed": False,
    "ai_analysis": {
        "is_running": False,
        "completed": False,
        "processed_articles": 0,
        "total_articles": 0,
        "current_article": ""
    }
}

scraped_content = []
analyzed_content = []

# [Keep all the existing helper functions: setup_regular_driver, setup_undetected_driver, 
# parse_time, parse_time_to_minutes, analyze_market_sentiment, get_impact_magnitude, 
# identify_affected_coins - exactly as they are in your original code]


def website1():
    global scraping_status
    driver = setup_undetected_driver()
    wait = WebDriverWait(driver, 20)
    try:
        article_data = []
        
        driver.get("https://cointelegraph.com/")
        time.sleep(3)

        # Scroll to load more content
        for _ in range(3):
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)

        # Get all URLs first
        url_elements = wait.until(EC.presence_of_all_elements_located((
            By.CSS_SELECTOR,
            'header[data-testid="post-card-header"] > a'
        )))
        
        urls = [url.get_attribute('href') for url in url_elements]
        print("\nInitial URLs found:", len(urls))
        
        # Get all dates
        date_elements = wait.until(EC.presence_of_all_elements_located((
            By.CSS_SELECTOR,
            'time[data-testid="post-card-published-date"]'
        )))
        dates = [date.text for date in date_elements]

        # Get all titles from main page
        title_elements = wait.until(EC.presence_of_all_elements_located((
            By.CSS_SELECTOR,
            'span[data-testid="post-card-title"]'
        )))
        titles = [title.text for title in title_elements]

        # Filter current news
        current_date = datetime.now()
        yesterday = current_date - timedelta(days=1)
        
        filtered_data = []
        for url, date, title in zip(urls, dates, titles):
            # Keep all relative time stamps (containing 'ago')
            if 'ago' in date.lower():
                filtered_data.append((date, url, title))
                continue
                
            # Parse the date string
            try:
                article_date = datetime.strptime(date, '%b %d, %Y')
                # Keep if date is today or yesterday
                if article_date.date() >= yesterday.date():
                    filtered_data.append((date, url, title))
            except ValueError:
                continue

        # Print filtered data
        print("\n=== Filtered Articles to Process ===")
        print(f"Total filtered articles: {len(filtered_data)}")
        print("-" * 100)
        for date, url, title in filtered_data:
            print(f"Date: {date}")
            print(f"Title: {title}")
            print(f"URL: {url}")
            print("-" * 100)

        # Update status with filtered count
        scraping_status["total_urls"] = len(filtered_data)
        scraping_status["processed_urls"] = 0
        
        for date, url, main_title in filtered_data:
            try:
                scraping_status["current_url"] = url
                scraping_status["processed_urls"] += 1
                print(f"\nProcessing ({scraping_status['processed_urls']}/{scraping_status['total_urls']}): {main_title}")
                
                driver.get(url)
                time.sleep(2)
                
                content = wait.until(EC.presence_of_all_elements_located((
                    By.CSS_SELECTOR,
                    '.post-content p, .post-content-wrapper p, .post_block p'
                )))
                
                article_text = '\n'.join([p.text for p in content if p.text.strip()])
                
                article_info = {
                    'title': main_title,
                    'url': url,
                    'date': date,
                    'content': article_text
                }
                article_data.append(article_info)
                
                print(f"✓ Successfully processed: {main_title}")
                
            except Exception as e:
                print(f"✗ Error processing URL - {url}: {str(e)}")
                continue
                
    except Exception as e:
        print(f"Main error: {str(e)}")
    
    finally:
        driver.quit()
        
    return article_data


def website3():
    import time
    import json
    from datetime import datetime, timedelta
    genai.configure(api_key="AIzaSyAyQ4DGoHTIDWgfUE5qXl8FNYgBS3hMG_g")

    model = genai.GenerativeModel(model_name="gemini-1.5-flash")
    driver = setup_undetected_driver()
    wait = WebDriverWait(driver, 10)
    driver.get("https://www.theblock.co/")
    time.sleep(3)  # Wait for initial page load

    # First collect all dates and their associated articles from the main page
    print("\n=== Collecting All Dates and Articles ===")
    initial_articles = []
    try:
        # Find all elements with the specific data-v attribute
        date_elements = driver.find_elements(
            By.CSS_SELECTOR, 'div[data-v-76acefb5].meta__wrapper'
        )
        for element in date_elements:
            try:
                date_text = element.text.strip()
                if not date_text:  # Skip empty dates
                    continue
                    
                # Get the parent article element
                parent_article = element.find_element(By.XPATH, "ancestor::article")
                
                # Try to get title from both possible headline classes
                try:
                    title = parent_article.find_element(By.CLASS_NAME, 'articleCard__headline').text
                except:
                    try:
                        title = parent_article.find_element(By.CLASS_NAME, 'textCard__headline').text
                    except:
                        continue
                
                # Get URL from the article
                url = parent_article.find_element(By.TAG_NAME, 'a').get_attribute('href')
                
                article_data = {
                    'title': title,
                    'date': date_text,
                    'url': url
                }
                
                print(f"Found article: {title}")
                print(f"Date: {date_text}")
                print(f"URL: {url}")
                print("-" * 40)
                
                if article_data not in initial_articles:
                    initial_articles.append(article_data)
                
            except Exception as e:
                continue
                
    except Exception as e:
        print(f"Error collecting initial articles: {str(e)}")

    current_date = datetime.now()
    yesterday = current_date - timedelta(days=1)
    
    filtered_articles = []
    for article in initial_articles:
        try:
            # Extract date from article's date_text (e.g., "DEC 08, 2024, 1:44PM EST • COMPANIES")
            date_parts = article['date'].split(',')  # Split by comma
            month_day = date_parts[0].strip()  # "DEC 08"
            year = date_parts[1].strip()  # "2024"
            time_part = date_parts[2].split('•')[0].strip()  # "1:44PM EST"
            
            # Combine into proper date string
            date_str = f"{month_day}, {year}"
            article_date = datetime.strptime(date_str, '%b %d, %Y')
            
            # Check if article is from today or yesterday
            if (article_date.date() == current_date.date() or 
                article_date.date() == yesterday.date()):
                filtered_articles.append(article)
                print(f"Keeping article from {date_str}")
            
        except Exception as e:
            continue

    # Replace initial_articles with filtered ones
    initial_articles = filtered_articles

    def extract_article_content(url):
        try:
            driver.get(url)
            time.sleep(2)  # Wait for content to load
            
            content = []
            
            # Get the main article container
            article_container = wait.until(EC.presence_of_element_located((
                By.CLASS_NAME, 'articleBody'
            )))
            
            # Try different selectors for text content
            selectors = [
                'span[data-v-c5594f84]',
                'span[data-v]',
                'p[data-v] span',
                '.articleContent span',
                '.articleBody p'
            ]
            
            for selector in selectors:
                elements = article_container.find_elements(By.CSS_SELECTOR, selector)
                for elem in elements:
                    text = elem.text.strip()
                    if (text and 
                        text != '=' and 
                        not text.startswith('—') and 
                        not 'Disclaimer' in text and 
                        not '@theblock.co' in text and 
                        not 'To contact' in text and
                        not '© 2024' in text and
                        not 'The Block' in text and
                        not 'Image:' in text and
                        not 'Illustration by' in text):
                        content.append(text)
            
            unique_content = []
            seen = set()
            for text in content:
                if text not in seen:
                    unique_content.append(text)
                    seen.add(text)
            
            return ' '.join(unique_content) if unique_content else "No content found."
            
        except Exception as e:
            print(f"Error extracting content from {url}: {str(e)}")
            return "Error extracting content."

    try:
        def convert_to_24hr(time_str):
            hour_str, period = time_str.split(":")
            hour = int(hour_str)
            minutes = int(period[:-2])
            period = period[-2:]
            
            if period == "PM" and hour != 12:
                hour += 12
            elif period == "AM" and hour == 12:
                hour = 0
                
            return hour * 60 + minutes

        latest_minutes = -1
        latest_article = None
        articles_data = []

        # Process all collected articles
        print("\n=== Processing Articles Content ===")
        for article in initial_articles:
            try:
                content = extract_article_content(article['url'])
                article_info = {
                    'title': article['title'],
                    'date': article['date'],
                    'url': article['url'],
                    'content': content
                }
                articles_data.append(article_info)
                
                # Update latest article
                try:
                    time_str = article['date'].split(", ")[1].split(" ")[0]
                    minutes = convert_to_24hr(time_str)
                    if minutes > latest_minutes:
                        latest_minutes = minutes
                        latest_article = article
                except:
                    continue
                    
            except Exception as e:
                print(f"Error processing article: {str(e)}")
                continue

        # Print JSON output before AI analysis
        print("\n=== Articles JSON Data ===")
        json_output = json.dumps(articles_data, indent=2)
        print(json_output)
        
        print("\n=== AI ANALYSIS ===\n")
        
        for article in articles_data:
            prompt = f"""
            First provide a 2-3 sentence summary of this crypto news article, then analyze potential market impact on major cryptocurrencies (BTC, ETH, SOL, XRP, etc.) in a concise bullet format:
            
            Title: {article['title']}
            Content: {article['content']}
            
            Format response as:
            SUMMARY: [2-3 sentence summary]
            
            POTENTIAL MARKET IMPACT:
            - [coin]: [predicted movement with brief reason]
            """
            
            response = model.generate_content(prompt)
            print(f"Analysis for: {article['title']}")
            print(f"Date: {article['date']}")
            print(f"{response.text}")
            print("-" * 80)
        
    except Exception as e:
        print(f"Error: {str(e)}")
    finally:
        driver.quit()
        
    return articles_data


def analyze_market_sentiment(text: str) -> str:
    """Helper function to analyze text sentiment"""
    positive_words = {'surge', 'jump', 'gain', 'rally', 'bull', 'upward', 'high', 'profit', 'success', 'grow', 'boost'}
    negative_words = {'drop', 'fall', 'decline', 'crash', 'bear', 'down', 'loss', 'risk', 'warning', 'trouble', 'concern'}
    
    text_lower = text.lower()
    positive_count = sum(1 for word in positive_words if word in text_lower)
    negative_count = sum(1 for word in negative_words if word in text_lower)
    
    if positive_count > negative_count:
        return "increase"
    elif negative_count > positive_count:
        return "decrease"
    return "stable"

def get_impact_magnitude(context: str) -> str:
    """Helper function to determine impact magnitude"""
    strong_words = {'massive', 'huge', 'significant', 'substantial', 'dramatic', 'major'}
    moderate_words = {'modest', 'moderate', 'slight', 'small', 'minor'}
    
    context_lower = context.lower()
    for word in strong_words:
        if word in context_lower:
            return "strongly"
    for word in moderate_words:
        if word in context_lower:
            return "slightly"
    return "moderately"


def identify_affected_coins(text: str) -> Dict[str, Dict[str, str]]:
    """Helper function to identify coins and their market impact"""
    crypto_keywords = {
        'Bitcoin': 'BTC',
        'Ethereum': 'ETH',
        'Cardano': 'ADA',
        'Dogecoin': 'DOGE',
        'Pepe': 'PEPE',
        'Fantom': 'FTM',
        'Sui': 'SUI',
        'Binance': 'BNB',
        'Solana': 'SOL',
        'Ripple': 'XRP',
        'Polygon': 'MATIC',
        'Chainlink': 'LINK',
        'Avalanche': 'AVAX',
        'Polkadot': 'DOT',
        'Litecoin': 'LTC'
    }
    
    affected_coins = {}
    text_lower = text.lower()
    
    for name, symbol in crypto_keywords.items():
        name_lower = name.lower()
        if name_lower in text_lower or symbol.lower() in text_lower:
            sentences = [s for s in text_lower.split('.') if name_lower in s or symbol.lower() in s]
            if sentences:
                direction = analyze_market_sentiment('. '.join(sentences))
                magnitude = get_impact_magnitude('. '.join(sentences))
                
                market_impact = f"{magnitude} {direction}"
                affected_coins[symbol] = {
                    "coin": symbol,
                    "market_impact": market_impact
                }
    
    return affected_coins

def combine_crypto_news():
    """Combines news from both sources and formats them consistently"""
    try:
        # Get data from both sources
        print("\n=== Fetching CoinTelegraph News ===")
        cointelegraph_data = website1()
        
        print("\n=== Fetching TheBlock News ===")
        theblock_data = website3()
        
        # Combine and standardize the data
        combined_articles = []
        
        # Process CoinTelegraph articles
        for article in cointelegraph_data:
            standardized_article = {
                'title': article['title'],
                'date': article['date'],
                'url': article['url'],
                'content': article['content'],
                'source': 'CoinTelegraph'
            }
            combined_articles.append(standardized_article)
        
        # Process TheBlock articles
        for article in theblock_data:
            standardized_article = {
                'title': article['title'],
                'date': article['date'],
                'url': article['url'],
                'content': article['content'],
                'source': 'TheBlock'
            }
            combined_articles.append(standardized_article)
        
        # Output combined JSON data
        print("\n=== Combined Crypto News Data ===")
        print(f"Total articles: {len(combined_articles)}")
        print(f"CoinTelegraph articles: {len(cointelegraph_data)}")
        print(f"TheBlock articles: {len(theblock_data)}")
        
        json_output = json.dumps(combined_articles, indent=2)
        print("\nJSON Output:")
        print(json_output)
        
        return combined_articles
        
    except Exception as e:
        print(f"Error combining crypto news: {str(e)}")
        return []

def analyze_combined_news(articles):
    """Analyzes the combined news articles using Gemini API"""
    global scraping_status
    
    analyzed_results = []
    
    try:
        # Configure Gemini
        genai.configure(api_key="AIzaSyAyQ4DGoHTIDWgfUE5qXl8FNYgBS3hMG_g")
        model = genai.GenerativeModel(model_name="gemini-1.5-flash")
        
        total_articles = len(articles)
        scraping_status["ai_analysis"]["total_articles"] = total_articles
        
        print("\n=== Starting Combined News Analysis ===")
        
        for idx, article in enumerate(articles, 1):
            try:
                # Update status
                scraping_status["ai_analysis"]["current_article"] = article["title"]
                scraping_status["ai_analysis"]["processed_articles"] = idx
                
                # Get coin analysis
                full_text = f"{article['title']} {article['content']}"
                coin_analysis = identify_affected_coins(full_text)
                
                # Get summary
                prompt = f"""
                Provide a concise 2-3 sentence summary of this crypto news article:
                
                Title: {article['title']}
                Content: {article['content']}
                """
                
                response = model.generate_content(prompt)
                
                analyzed_article = {
                    'title': article['title'],
                    'url': article['url'],
                    'date': article['date'],
                    'content': article['content'],
                    'source': article['source'],
                    'summary': response.text,
                    'coin_analysis': coin_analysis
                }
                
                analyzed_results.append(analyzed_article)
                
                print(f"\nAnalyzed article {idx}/{total_articles}")
                print(f"Source: {article['source']}")
                print(f"Title: {article['title']}")
                print(f"Summary: {response.text}")
                print("Coin Analysis:", json.dumps(coin_analysis, indent=2))
                print("-" * 80)
                
                time.sleep(1)  # Rate limiting
                
            except Exception as e:
                print(f"Error analyzing article '{article['title']}': {str(e)}")
                continue
                
        return analyzed_results
        
    except Exception as e:
        print(f"Error in news analysis: {str(e)}")
        return []

def combined_scraping_task():
    """Main task that coordinates scraping and analysis"""
    global scraping_status, scraped_content, analyzed_content
    
    scraping_status["is_running"] = True
    scraping_status["completed"] = False
    
    try:
        # Get combined news
        print("Starting combined news collection...")
        combined_articles = combine_crypto_news()
        scraped_content = combined_articles
        
        # Update scraping status
        scraping_status["total_urls"] = len(combined_articles)
        scraping_status["processed_urls"] = len(combined_articles)
        scraping_status["completed"] = True
        
        # Start analysis
        print("Starting combined news analysis...")
        scraping_status["ai_analysis"]["is_running"] = True
        analyzed_content = analyze_combined_news(combined_articles)
        
        # Update analysis status
        scraping_status["ai_analysis"]["completed"] = True
        
    except Exception as e:
        print(f"Error in combined scraping task: {str(e)}")
    finally:
        scraping_status["is_running"] = False
        scraping_status["ai_analysis"]["is_running"] = False

# Flask Routes
@app.route('/crypto/start')
def start_combined_scraping():
    global scraping_status
    
    if scraping_status["is_running"]:
        return jsonify({
            'status': 'error',
            'message': 'Scraping is already in progress'
        })
    
    # Reset status
    scraping_status["ai_analysis"] = {
        "is_running": False,
        "completed": False,
        "processed_articles": 0,
        "total_articles": 0,
        "current_article": ""
    }
    
    # Start combined scraping in a thread
    thread = Thread(target=combined_scraping_task)
    thread.start()
    
    return jsonify({
        'status': 'success',
        'message': 'Combined crypto news scraping started'
    })

@app.route('/crypto/status')
def get_combined_status():
    return jsonify({
        'status': 'success',
        'data': {
            'scraping': {
                'is_running': scraping_status["is_running"],
                'total_urls': scraping_status["total_urls"],
                'processed_urls': scraping_status["processed_urls"],
                'current_url': scraping_status["current_url"],
                'completed': scraping_status["completed"]
            },
            'ai_analysis': scraping_status["ai_analysis"]
        }
    })

@app.route('/crypto/content')
def get_combined_content():
    if scraping_status["is_running"]:
        return jsonify({
            'status': 'pending',
            'message': 'Scraping is still in progress'
        })
    
    if not scraping_status["completed"]:
        return jsonify({
            'status': 'error',
            'message': 'No scraping has been performed yet'
        })
    
    if scraping_status["ai_analysis"]["completed"]:
        return jsonify({
            'status': 'success',
            'data': analyzed_content
        })
    elif scraping_status["ai_analysis"]["is_running"]:
        return jsonify({
            'status': 'pending',
            'message': 'AI analysis in progress',
            'data': scraped_content
        })
    else:
        return jsonify({
            'status': 'success',
            'data': scraped_content
        })

@app.route('/crypto/summary')
def get_combined_summary():
    if scraping_status["is_running"]:
        return jsonify({
            'status': 'pending',
            'message': 'Scraping is still in progress'
        })
    
    if not scraping_status["completed"]:
        return jsonify({
            'status': 'error',
            'message': 'No scraping has been performed yet'
        })
    
    if not scraping_status["ai_analysis"]["completed"]:
        if scraping_status["ai_analysis"]["is_running"]:
            return jsonify({
                'status': 'pending',
                'message': 'AI analysis in progress'
            })
        return jsonify({
            'status': 'error',
            'message': 'AI analysis has not been performed'
        })
    
    # Format summary data
    summary_data = [
        {
            'title': article['title'],
            'url': article['url'],
            'date': article['date'],
            'source': article['source'],
            'summary': article['summary'],
            'coin_analysis': article['coin_analysis']
        }
        for article in analyzed_content
    ]
    
    return jsonify({
        'status': 'success',
        'data': summary_data
    })

if __name__ == '__main__':
    app.run(debug=True)