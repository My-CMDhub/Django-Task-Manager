#!/bin/bash

# Install required packages
pip install -r requirements.txt

# Create Django migrations for the chatbot app
python manage.py makemigrations chatbot_app
python manage.py migrate chatbot_app

# Download NLTK data
python -c "import nltk; nltk.download(['punkt', 'averaged_perceptron_tagger', 'popular', 'averaged_perceptron_tagger_eng'])"

# Initialize the chatbot
python manage.py shell -c "from chatbot_app.initialize import init_index_from_url; init_index_from_url(['https://docs.djangoproject.com/en/4.2/topics/db/models/'], None)"

echo "Chatbot setup complete!" 