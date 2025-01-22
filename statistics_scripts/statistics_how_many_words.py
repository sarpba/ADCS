import os
import string
import sys
from collections import Counter

def normalize_text(text):
    """Normalize the text by converting to lowercase and removing punctuation."""
    text = text.lower()  # Convert to lowercase
    text = text.translate(str.maketrans("", "", string.punctuation))  # Remove punctuation
    return text

def collect_words_from_txt_files(directory):
    """Collect and count unique words from all .txt files in the directory and subdirectories."""
    word_counter = Counter()
    
    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith('.txt'):
                file_path = os.path.join(root, file)
                with open(file_path, 'r', encoding='utf-8') as f:
                    text = f.read()
                    normalized_text = normalize_text(text)
                    words = normalized_text.split()
                    word_counter.update(words)
    
    return word_counter

def main(directory):
    word_counter = collect_words_from_txt_files(directory)
    
    # Total number of words
    total_words = sum(word_counter.values())
    
    # Number of unique words
    unique_word_count = len(word_counter)
    
    # Frequency of each word (1 time, 2 times, ..., 10 times and more than 10 times)
    frequency_count = Counter(word_counter.values())
    
    print(f"Total words: {total_words}")
    print(f"Total unique words: {unique_word_count}")
    
    for i in range(1, 11):
        print(f"Number of words appearing {i} time(s): {frequency_count.get(i, 0)}")
    
    # Words that appear more than 10 times
    more_than_ten = sum(count for freq, count in frequency_count.items() if freq > 10)
    print(f"Number of words appearing more than 10 times: {more_than_ten}")

if __name__ == '__main__':
    if len(sys.argv) != 2:
        print("Usage: python script.py /dir")
    else:
        input_directory = sys.argv[1]
        main(input_directory)
