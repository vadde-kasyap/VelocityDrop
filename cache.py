import redis

redis_client = redis.Redis(host='localhost', port=6379, decode_responses=True)

class TrieNode:
    def __init__(self):
        self.children = {}
        self.is_end_of_word = False

class Trie:
    def __init__(self):
        self.root = TrieNode()
        
    def insert(self, word):
        node = self.root
        for char in word:
            if char not in node.children:
                node.children[char] = TrieNode()
            node = node.children[char]
        node.is_end_of_word = True
        
    def search_prefix(self, prefix):
        node = self.root
        for char in prefix:
            if char not in node.children:
                return []
            node = node.children[char]
        return self.collections_all_words(node, prefix)
        
    def collections_all_words(self, node, current_prefix):
        results = []
        if node.is_end_of_word:
            results.append(current_prefix)
        for char, child_node in node.children.items():
            results.extend(self.collections_all_words(child_node, current_prefix + char))        
        return results

search_trie = Trie()
