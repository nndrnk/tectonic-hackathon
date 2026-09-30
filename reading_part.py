
import os

base_dir = os.path.dirname(os.path.abspath(__file__))
my_folder = os.path.join(base_dir, "data")


def get_words(text_file_name):
    with open(text_file_name, "r", encoding="utf-8") as f:
        content = f.read()
    word_list = content.split()
    return text_file_name, word_list


def get_all_files(folder):
    """Return a dictionary {file_name: word_list}
    for all .txt files in the folder."""
    result = {}
    for name in os.listdir(folder):
        if name.endswith(".txt"):
            file_path = os.path.join(folder, name)
            _, words = get_words(file_path)
            result[name] = words
    return result


if __name__ == "__main__":
    texts = get_all_files(my_folder)
    print(texts)
