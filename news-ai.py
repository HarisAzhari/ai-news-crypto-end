import sqlite3
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
import time
import requests
from bs4 import BeautifulSoup
import json
from flask import Flask, jsonify
from threading import Thread
from typing import Dict, List, Any
from flask_cors import CORS
import feedparser
import os

app = Flask(__name__)
CORS(app)

DB_PATH = 'crypto_news.db'

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

def init_db():
    """Initialize the SQLite database with required tables"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # Create articles table
    c.execute('''
        CREATE TABLE IF NOT EXISTS articles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            url TEXT UNIQUE NOT NULL,
            date TEXT NOT NULL,
            content TEXT NOT NULL,
            source TEXT NOT NULL,
            image_url TEXT,
            summary TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Create coin_analysis table
    c.execute('''
        CREATE TABLE IF NOT EXISTS coin_analysis (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            article_id INTEGER NOT NULL,
            coin TEXT NOT NULL,
            market_impact TEXT NOT NULL,
            FOREIGN KEY (article_id) REFERENCES articles (id) ON DELETE CASCADE,
            UNIQUE(article_id, coin)
        )
    ''')
    
    conn.commit()
    conn.close()

def store_analyzed_article(article: dict) -> bool:
    """Store an analyzed article and its coin analysis in the database"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    success = False
    
    try:
        # Check if article already exists
        c.execute('SELECT id FROM articles WHERE url = ?', (article['url'],))
        existing = c.fetchone()
        
        if existing:
            print(f"Article already exists: {article['title']}")
            return False
        
        # Insert article
        c.execute('''
            INSERT INTO articles 
            (title, url, date, content, source, image_url, summary)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            article['title'],
            article['url'],
            article['date'],
            article['content'],
            article['source'],
            article.get('image_url', ''),
            article.get('summary', '')
        ))
        
        article_id = c.lastrowid
        
        # Insert coin analysis
        if 'coin_analysis' in article:
            for coin_data in article['coin_analysis'].values():
                c.execute('''
                    INSERT INTO coin_analysis 
                    (article_id, coin, market_impact)
                    VALUES (?, ?, ?)
                ''', (
                    article_id,
                    coin_data['coin'],
                    coin_data['market_impact']
                ))
        
        conn.commit()
        success = True
        
    except Exception as e:
        print(f"Error storing article in database: {str(e)}")
        conn.rollback()
    finally:
        conn.close()
        return success

def get_stored_articles(limit: int = 50) -> List[Dict]:
    """Retrieve stored articles from the database"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    try:
        c.execute('''
            SELECT 
                a.*, 
                GROUP_CONCAT(ca.coin || ':' || ca.market_impact) as coin_impacts
            FROM articles a
            LEFT JOIN coin_analysis ca ON a.id = ca.article_id
            GROUP BY a.id
            ORDER BY a.created_at DESC
            LIMIT ?
        ''', (limit,))
        
        rows = c.fetchall()
        articles = []
        
        for row in rows:
            article = dict(row)
            
            # Convert coin_impacts string to coin_analysis dict
            coin_analysis = {}
            if article['coin_impacts']:
                for impact in article['coin_impacts'].split(','):
                    coin, market_impact = impact.split(':')
                    coin_analysis[coin] = {
                        "coin": coin,
                        "market_impact": market_impact
                    }
            
            # Remove the temporary coin_impacts field
            del article['coin_impacts']
            article['coin_analysis'] = coin_analysis
            articles.append(article)
        
        return articles
        
    finally:
        conn.close()

def setup_headless_driver():
    """Setup Chrome in headless mode"""
    chrome_options = webdriver.ChromeOptions()
    chrome_options.add_argument('--headless=new')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    return webdriver.Chrome(options=chrome_options)

def website1():
    """Scrapes CoinTelegraph news"""
    try:
        article_data = []
        
        rss_url = "https://cointelegraph.com/rss"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        response = requests.get(rss_url, headers=headers)
        if response.status_code != 200:
            raise Exception(f"RSS request failed with status code: {response.status_code}")
            
        feed = feedparser.parse(response.content)
        current_date = datetime.now()
        yesterday = current_date - timedelta(days=1)
        
        filtered_data = []
        for item in feed.entries:
            pub_date = datetime.strptime(item.published, '%a, %d %b %Y %H:%M:%S %z')
            pub_date = pub_date.replace(tzinfo=None)
            
            if pub_date.date() >= yesterday.date():
                image_url = None
                if hasattr(item, 'media_content'):
                    image_url = item.media_content[0]['url']
                
                filtered_data.append({
                    'date': pub_date.strftime('%b %d, %Y'),
                    'url': item.link,
                    'title': item.title,
                    'image_url': image_url
                })
        
        for article in filtered_data:
            try:
                article_response = requests.get(article['url'], headers=headers)
                if article_response.status_code != 200:
                    continue
                    
                soup = BeautifulSoup(article_response.text, 'html.parser')
                content_elements = soup.select('.post-content p')
                article_text = '\n'.join([p.get_text().strip() for p in content_elements if p.get_text().strip()])
                
                if article_text:
                    article_info = {
                        'title': article['title'],
                        'url': article['url'],
                        'date': article['date'],
                        'content': article_text,
                        'image_url': article['image_url'],
                        'source': 'CoinTelegraph'
                    }
                    article_data.append(article_info)
                time.sleep(1)
                
            except Exception as e:
                print(f"Error processing URL - {article['url']}: {str(e)}")
                continue
                
        return article_data
                
    except Exception as e:
        print(f"Error in CoinTelegraph scraping: {str(e)}")
        return []

def website10():
    """Scrapes TheDefiant news"""
    try:
        rss_url = "https://thedefiant.io/api/feed"
        article_data = []
        
        print("\n=== Collecting Articles from TheDefiant ===")
        
        feed = feedparser.parse(rss_url)
        current_date = datetime.now()
        yesterday = current_date - timedelta(days=1)
        
        filtered_data = []
        for entry in feed.entries:
            try:
                pub_date = datetime.strptime(entry.published, '%a, %d %b %Y %H:%M:%S %Z')
                if pub_date.replace(tzinfo=None) >= yesterday:
                    content = entry.content[0].value if hasattr(entry, 'content') else entry.summary
                    image_url = entry.media_thumbnail[0]['url'] if hasattr(entry, 'media_thumbnail') else None
                    
                    filtered_data.append({
                        'date': pub_date.strftime('%b %d, %Y'),
                        'url': entry.link,
                        'title': entry.title,
                        'content': content,
                        'image_url': image_url,
                        'source': 'TheDefiant'
                    })
            except ValueError:
                continue
        
        print(f"Found {len(filtered_data)} recent articles from TheDefiant")
        print(json.dumps(filtered_data, indent=2))
        return filtered_data
        
    except Exception as e:
        print(f"Error in TheDefiant scraping: {str(e)}")
        return []

def website11():
    """Scrapes Protos news using headless Selenium"""
    driver = setup_headless_driver()
    wait = WebDriverWait(driver, 20)
    driver.get("https://protos.com/")
    time.sleep(3)

    today = datetime.now()
    yesterday = today - timedelta(days=1)
    target_date = yesterday.strftime("%b %d, %Y")
    filtered_data = []

    try:
        articles = wait.until(EC.presence_of_all_elements_located((
            By.CSS_SELECTOR, 'article.b-container__main'
        )))
        seen_titles = set()
        
        for article in articles:
            try:
                time_element = article.find_element(By.CSS_SELECTOR, 'div.s-links-2 time')
                title_element = article.find_element(By.CSS_SELECTOR, 'h1.u-heading-1 a')
                
                datetime_text = time_element.text if time_element else None
                title_text = title_element.text if title_element else None
                url = title_element.get_attribute('href')
                article_date = datetime_text.split('•')[1].strip() if datetime_text else None
                
                if article_date == target_date and title_text and title_text not in seen_titles:
                    seen_titles.add(title_text)
                    driver.get(url)
                    time.sleep(2)
                    
                    content_elements = driver.find_elements(By.CSS_SELECTOR, 'div.s-single p')
                    content = ' '.join([p.text for p in content_elements if p.text.strip()])
                    
                    try:
                        image_element = driver.find_element(By.CSS_SELECTOR, 'img.wp-post-image')
                        srcset = image_element.get_attribute('srcset')
                        if srcset:
                            srcset_pairs = [pair.strip().split(' ') for pair in srcset.split(',')]
                            largest_image = max(srcset_pairs, key=lambda x: int(x[1].replace('w', '')))
                            image_url = largest_image[0]
                        else:
                            image_url = image_element.get_attribute('src')
                    except:
                        image_url = None
                    
                    filtered_data.append({
                        'date': article_date,
                        'url': url,
                        'title': title_text,
                        'content': content,
                        'image_url': image_url,
                        'source': 'Protos'
                    })
                    
                    driver.back()
                    time.sleep(2)
                    
            except Exception as e:
                print(f"Error processing article: {str(e)}")
                continue
                
    except Exception as e:
        print(f"Main error: {str(e)}")
    finally:
        driver.quit()

    print(f"Found {len(filtered_data)} recent articles from Protos")
    print(json.dumps(filtered_data, indent=2))
    return filtered_data

def is_market_significant_news(title: str, content: str, model) -> bool:
    """Uses Gemini to determine if a crypto news article has significant market impact"""
    prompt = f"""
    Analyze this crypto news article and determine if it has significant market impact.
    Only respond with "y" if ALL of these criteria are met:
    1. The news is directly related to cryptocurrency or blockchain
    2. The news could affect market prices or trading behavior
    3. The impact is significant (e.g. involves major amounts >$10M, affects major protocols/exchanges, regulatory changes)
    4. The news affects the broader crypto market, not just individual small incidents
    
    Respond with "n" if the news:
    - Only affects individual users or small amounts
    - Is about minor scams or personal losses
    - Is primarily educational or informational
    - Has minimal broader market impact
    - Is about minor technical updates or small projects
    
    Only reply with "y" or "n" - no other explanation.
    
    Title: {title}
    Content: {content}
    """
    
    max_retries = 3
    base_delay = 60
    
    for attempt in range(max_retries):
        try:
            response = model.generate_content(prompt)
            return response.text.strip().lower() == 'y'
        except Exception as e:
            if "429" in str(e) and attempt < max_retries - 1:
                wait_time = base_delay * (attempt + 1)
                print(f"\nRate limit reached. Waiting {wait_time} seconds...")
                time.sleep(wait_time)
                continue
            else:
                print(f"Error checking market significance: {str(e)}")
                return True
    
    return True

def analyze_market_sentiment(text: str) -> str:
    """Analyzes text sentiment for market impact"""
    positive_words = {'surge', 'jump', 'gain', 'rally', 'bull', 'upward', 'high', 'profit', 'success', 'grow', 'boost'}
    negative_words = {'drop', 'fall', 'decline', 'crash', 'bear', 'down', 'loss', 'risk', 'warning', 'trouble'}
    
    text_lower = text.lower()
    positive_count = sum(1 for word in positive_words if word in text_lower)
    negative_count = sum(1 for word in negative_words if word in text_lower)
    
    if positive_count > negative_count:
        return "increase"
    elif negative_count > positive_count:
        return "decrease"
    return "stable"

import re
def get_impact_magnitude(context: str) -> str:
    """Determines impact magnitude of news"""
    strong_words = {'massive', 'huge', 'significant', 'substantial', 'dramatic', 'major'}
    moderate_words = {'modest', 'moderate', 'slight', 'small', 'minor', 'limited'}
    
    context_lower = context.lower()
    
    amount_pattern = r'\$(\d+(?:\.\d+)?)\s*(?:million|billion|trillion|M|B|T)'
    matches = re.findall(amount_pattern, context)
    
    if matches:
        for amount in matches:
            try:
                value = float(amount)
                if value > 100:
                    return "strongly"
                elif value > 10:
                    return "moderately"
            except ValueError:
                continue
    
    for word in strong_words:
        if word in context_lower:
            return "strongly"
    for word in moderate_words:
        if word in context_lower:
            return "slightly"
    
    return "moderately"

def identify_affected_coins(text: str) -> Dict[str, Dict[str, str]]:
    """Identifies coins and their market impact"""
    crypto_keywords = {
        'Bitcoin': 'BTC',
        'Ethereum': 'ETH',
        'Cardano': 'ADA',
        'Binance': 'BNB',
        'Solana': 'SOL',
        'Ripple': 'XRP',
        'Polygon': 'MATIC',
        'Chainlink': 'LINK',
        'Avalanche': 'AVAX',
        'Polkadot': 'DOT'
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
    """Combines and filters news from all sources"""
    filtered_articles = []
    
    # Configure Gemini
    genai.configure(api_key="AIzaSyAyQ4DGoHTIDWgfUE5qXl8FNYgBS3hMG_g")  # Replace with your API key
    model = genai.GenerativeModel(model_name="gemini-1.5-flash")
    
    # Fetch CoinTelegraph News
    try:
        print("\n=== Fetching CoinTelegraph News ===")
        cointelegraph_data = website1()
        print(f"Successfully fetched {len(cointelegraph_data)} articles from CoinTelegraph")
        
        for article in cointelegraph_data:
            if is_market_significant_news(article['title'], article['content'], model):
                filtered_articles.append(article)
            else:
                print(f"Filtered out low-impact article from CoinTelegraph: {article['title']}")
    
    except Exception as e:
        print(f"Error processing CoinTelegraph news: {str(e)}")
    
    # Fetch Protos News
    try:
        print("\n=== Fetching Protos News ===")
        protos_data = website11()
        print(f"Successfully fetched {len(protos_data)} articles from Protos")
        
        for article in protos_data:
            if is_market_significant_news(article['title'], article['content'], model):
                filtered_articles.append(article)
            else:
                print(f"Filtered out low-impact article from Protos: {article['title']}")
    
    except Exception as e:
        print(f"Error processing Protos news: {str(e)}")
    
    # Fetch TheDefiant News
    try:
        print("\n=== Fetching TheDefiant News ===")
        thedefiant_data = website10()
        print(f"Successfully fetched {len(thedefiant_data)} articles from TheDefiant")
        
        for article in thedefiant_data:
            if is_market_significant_news(article['title'], article['content'], model):
                filtered_articles.append(article)
            else:
                print(f"Filtered out low-impact article from TheDefiant: {article['title']}")
            
    except Exception as e:
        print(f"Error processing TheDefiant news: {str(e)}")
    
    print(f"\nTotal market-significant articles after filtering: {len(filtered_articles)}")
    print("\n====== Combined JSON Output ======\n")
    print(json.dumps(filtered_articles, indent=2))
    
    return filtered_articles

def analyze_combined_news(articles):
    """Analyzes the combined news articles using Gemini API"""
    global scraping_status
    analyzed_results = []
    
    try:
        genai.configure(api_key="AIzaSyAOTr-EJIgfj3vbQWZJ5QvoyAsgJaBL4ak")
        model = genai.GenerativeModel(model_name="gemini-1.5-flash")
        
        total_articles = len(articles)
        scraping_status["ai_analysis"]["total_articles"] = total_articles
        
        print("\n=== Starting Combined News Analysis ===")
        
        for idx, article in enumerate(articles, 1):
            try:
                scraping_status["ai_analysis"]["current_article"] = article["title"]
                scraping_status["ai_analysis"]["processed_articles"] = idx
                
                analysis_prompt = f"""
                Provide a concise but comprehensive analysis of this crypto news article.
                Focus on market impact, potential price effects, and broader implications.
                Limit response to 3-4 sentences.
                
                Title: {article['title']}
                Content: {article['content']}
                """
                
                max_retries = 3
                base_delay = 60
                
                for attempt in range(max_retries):
                    try:
                        response = model.generate_content(analysis_prompt)
                        break
                    except Exception as e:
                        if "429" in str(e) and attempt < max_retries - 1:
                            wait_time = base_delay * (attempt + 1)
                            print(f"\nRate limit reached. Waiting {wait_time} seconds...")
                            time.sleep(wait_time)
                            continue
                        raise e
                
                full_text = f"{article['title']} {article['content']}"
                coin_analysis = identify_affected_coins(full_text)
                
                analyzed_article = {
                    'title': article['title'],
                    'url': article['url'],
                    'date': article['date'],
                    'content': article['content'],
                    'source': article['source'],
                    'image_url': article.get('image_url', ''),
                    'summary': response.text,
                    'coin_analysis': coin_analysis
                }
                
                if store_analyzed_article(analyzed_article):
                    analyzed_results.append(analyzed_article)
                
                print(f"\nAnalyzed article {idx}/{total_articles}")
                print(f"Source: {article['source']}")
                print(f"Title: {article['title']}")
                print("Coin Analysis:", json.dumps(coin_analysis, indent=2))
                print("-" * 80)
                
                time.sleep(2)
                
            except Exception as e:
                print(f"Error analyzing article '{article['title']}': {str(e)}")
                continue
                
        return analyzed_results
        
    except Exception as e:
        print(f"Error in news analysis: {str(e)}")
        return []

def combined_scraping_task():
    """Main task that coordinates scraping and analysis"""
    global scraping_status
    
    scraping_status["is_running"] = True
    scraping_status["completed"] = False
    scraping_status["ai_analysis"]["is_running"] = False
    scraping_status["ai_analysis"]["completed"] = False
    
    try:
        print("Starting combined news collection...")
        combined_articles = combine_crypto_news()
        
        scraping_status["total_urls"] = len(combined_articles)
        scraping_status["processed_urls"] = len(combined_articles)
        scraping_status["completed"] = True
        
        print("Starting combined news analysis...")
        scraping_status["ai_analysis"]["is_running"] = True
        analyzed_content = analyze_combined_news(combined_articles)
        scraping_status["ai_analysis"]["completed"] = True
        
    except Exception as e:
        print(f"Error in combined scraping task: {str(e)}")
    finally:
        scraping_status["is_running"] = False
        scraping_status["ai_analysis"]["is_running"] = False

# Flask Routes
@app.route('/crypto/start')
def start_combined_scraping():
    """Start the scraping process"""
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
    
    thread = Thread(target=combined_scraping_task)
    thread.daemon = True
    thread.start()
    
    return jsonify({
        'status': 'success',
        'message': 'Combined crypto news scraping started'
    })

@app.route('/crypto/status')
def get_combined_status():
    """Get current scraping status"""
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

@app.route('/crypto/summary')
def get_combined_summary():
    """Get analyzed articles from database"""
    if scraping_status["ai_analysis"]["is_running"]:
        return jsonify({
            'status': 'pending',
            'message': 'AI analysis in progress'
        })
    
    stored_articles = get_stored_articles()
    
    if not stored_articles:
        return jsonify({
            'status': 'error',
            'message': 'No analyzed articles found in database'
        })
    
    return jsonify({
        'status': 'success',
        'data': stored_articles
    })

@app.route('/crypto/<coin>')
def get_coin_stats(coin):
    """Get 7-day statistics for a specific coin from analyzed articles"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    try:
        # Calculate date 7 days ago
        seven_days_ago = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
        
        # Get all impact analysis for the specified coin within last 7 days
        c.execute('''
            SELECT 
                a.date,
                ca.market_impact,
                COUNT(*) as count
            FROM articles a
            JOIN coin_analysis ca ON a.id = ca.article_id
            WHERE ca.coin = ?
            AND date(a.created_at) >= date(?)
            GROUP BY a.date, ca.market_impact
            ORDER BY a.date DESC
        ''', (coin.upper(), seven_days_ago))
        
        results = c.fetchall()
        
        if not results:
            return jsonify({
                'status': 'error',
                'message': f'No analysis found for {coin.upper()} in the last 7 days'
            })
        
        # Organize data by date
        date_stats = {}
        total_mentions = 0
        
        for row in results:
            date = row['date']
            impact = row['market_impact']
            count = row['count']
            total_mentions += count
            
            if date not in date_stats:
                date_stats[date] = {
                    'strongly_increase': 0,
                    'strongly_decrease': 0,
                    'strongly_stable': 0,
                    'moderately_increase': 0,
                    'moderately_decrease': 0,
                    'moderately_stable': 0,
                    'slightly_increase': 0,
                    'slightly_decrease': 0,
                    'slightly_stable': 0
                }
            
            date_stats[date][impact] = count
        
        # Format response
        formatted_data = {
            'total_news_mention': total_mentions,
            'data': {
                date: {
                    'date': date,
                    'coin': coin.upper(),
                    'market_impact': stats
                }
                for date, stats in date_stats.items()
            }
        }
        
        return jsonify({
            'status': 'success',
            'data': formatted_data
        })
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        })
    finally:
        conn.close()

if __name__ == '__main__':
    init_db()
    port = int(os.environ.get('PORT', 8000))
    app.run(host='0.0.0.0', port=port)

