import nltk

def download_nltk_data():
    # List of necessary NLTK datasets
    nltk_data = ['punkt', 'punkt_tab', 'averaged_perceptron_tagger']
    
    for data in nltk_data:
        nltk.download(data)

if __name__ == '__main__':
    download_nltk_data()
