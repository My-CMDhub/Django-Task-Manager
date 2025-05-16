import os
import nltk
from llama_index.llms.openai import OpenAI
from llama_index import VectorStoreIndex, SimpleDirectoryReader
from llama_index import StorageContext, load_index_from_storage
from llama_index import ServiceContext
from langchain_community.document_loaders import SeleniumURLLoader
from selenium import webdriver
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Download NLTK data if not already downloaded
try:
    nltk.data.find('tokenizers/punkt')
except LookupError:
    nltk.download(['punkt', 'averaged_perceptron_tagger', 'popular'])
    nltk.download('averaged_perceptron_tagger_eng')

def init_index_from_url(urls, openai_api_key=None):
    """
    Initialize the vector index from website URLs.
    
    Args:
        urls (list): List of URLs to scrape for data
        openai_api_key (str, optional): OpenAI API key. If None, tries to use from environment.
        
    Returns:
        VectorStoreIndex: The created index, or None if there was an error
    """
    try:
        # Set API key from parameter or environment
        if openai_api_key:
            os.environ["OPENAI_API_KEY"] = openai_api_key
        else:
            openai_api_key = os.getenv('OPENAI_API_KEY')
            
        if not openai_api_key:
            print("⚠️ No OpenAI API key provided. Please set OPENAI_API_KEY.")
            return None
        
        print(f"🔄 Starting to scrape {len(urls)} URLs...")
        
        # Step 1: Web scraping
        documents = []
        for url in urls:
            loader = SeleniumURLLoader(urls=[url])
            documents.extend(loader.load())
            print(f"✓ Successfully scraped: {url}")

        # Step 2: Save raw text
        input_dir = "data"
        os.makedirs(input_dir, exist_ok=True)
        data_str = '\n'.join(doc.page_content for doc in documents)
        with open(os.path.join(input_dir, "data.txt"), "w") as file:
            file.write(data_str)
        print("✓ Raw data saved to data/data.txt")

        # Step 3: Create embeddings and index
        try:
            # Use simple OpenAI initialization without proxies
            llm = OpenAI(
                model="gpt-3.5-turbo", 
                temperature=0.7,
                max_tokens=512,
                api_key=openai_api_key
            )
            service_context = ServiceContext.from_defaults(llm=llm)
            documents = SimpleDirectoryReader(input_dir).load_data()
            index = VectorStoreIndex.from_documents(documents, service_context=service_context, show_progress=True)
            print("✓ Index created successfully")
            
            # Step 4: Save the index to disk
            index.storage_context.persist('PKL_file')
            print("✓ Index saved to PKL_file directory")
            
            return index
        except Exception as e:
            print(f"❌ Error in index creation: {str(e)}")
            raise

    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return None

def load_index_from_disk():
    """
    Load the vector index from disk.
    
    Returns:
        VectorStoreIndex: The loaded index
    """
    try:
        storage_context = StorageContext.from_defaults(persist_dir="PKL_file")
        index = load_index_from_storage(storage_context)
        print("✓ Index loaded successfully")
        return index
    except Exception as e:
        print(f"❌ Error loading index: {str(e)}")
        return None

if __name__ == "__main__":
    # Example usage:
    urls = [ "http://127.0.0.1:8000/"]
    init_index_from_url(urls) 