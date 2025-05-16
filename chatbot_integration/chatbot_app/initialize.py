import os
import nltk
from llama_index.llms.mistralai import MistralAI
from llama_index.embeddings.mistralai import MistralAIEmbedding
from llama_index.core import Settings, VectorStoreIndex
from llama_index.core import SimpleDirectoryReader
from llama_index.core import StorageContext
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

def init_index_from_url(urls, mistral_api_key=None):
    """
    Initialize the vector index from website URLs.
    
    Args:
        urls (list): List of URLs to scrape for data
        mistral_api_key (str, optional): Mistral API key. If None, tries to use from environment.
        
    Returns:
        VectorStoreIndex: The created index, or None if there was an error
    """
    try:
        # Set API key from parameter or environment
        if mistral_api_key:
            # Ensure LlamaIndex components can see it if they don't take it directly
            os.environ["MISTRAL_API_KEY"] = mistral_api_key
        else:
            mistral_api_key = os.getenv('MISTRAL_API_KEY')
            
        if not mistral_api_key:
            print("⚠️ No Mistral API key provided. Please set MISTRAL_API_KEY.")
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
        Settings.llm = MistralAI(api_key=mistral_api_key, model="mistral-small-latest", max_tokens=512, temperature=0.7)
        Settings.embed_model = MistralAIEmbedding(api_key=mistral_api_key, model_name="mistral-embed")
        
        documents = SimpleDirectoryReader(input_dir).load_data()
        index = VectorStoreIndex.from_documents(documents, show_progress=True)
        print("✓ Index created successfully")
        
        # Step 4: Save the index to disk
        index.storage_context.persist('PKL_file')
        print("✓ Index saved to PKL_file directory")
        
        return index

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
    urls = [ " http://127.0.0.1:8000/"]
    init_index_from_url(urls) 