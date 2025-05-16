import os
from llama_index import VectorStoreIndex, SimpleDirectoryReader
from llama_index import StorageContext, load_index_from_storage

# Create a fresh index from the data and save it
def create_index():
    try:
        # Step 1: Load the documents
        print("Loading documents...")
        documents = SimpleDirectoryReader("data").load_data()
        print(f"Loaded {len(documents)} documents")
        
        # Step 2: Create the index
        print("Creating index...")
        index = VectorStoreIndex.from_documents(documents)
        print("Index created successfully")
        
        # Step 3: Save the index
        print("Saving index...")
        index.storage_context.persist("PKL_file")
        print("Index saved successfully")
        
        return True
    except Exception as e:
        print(f"Error creating index: {e}")
        return False

# Attempt to load an existing index
def load_index():
    try:
        print("Loading index from PKL_file...")
        storage_context = StorageContext.from_defaults(persist_dir="PKL_file")
        index = load_index_from_storage(storage_context)
        print("Index loaded successfully")
        
        # Test the index
        query_engine = index.as_query_engine()
        response = query_engine.query("What is a Django model?")
        print(f"Test query response: {response}")
        
        return True
    except Exception as e:
        print(f"Error loading index: {e}")
        return False

if __name__ == "__main__":
    # First try to load an existing index
    if not load_index():
        print("Creating a new index since loading failed...")
        create_index() 