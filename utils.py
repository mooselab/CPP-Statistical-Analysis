import re

def get_element_texts(element):
    if element is None:
        return ''
    return re.sub(' +', ' ', ''.join(element.itertext()).strip().replace('\n', '').replace('\t', ''))