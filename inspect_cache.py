
import pickle
import os
import sys

# Add src path
sys.path.append(os.getcwd())

cache_path = 'data/cache/revenue_cache.pkl'
if os.path.exists(cache_path):
    with open(cache_path, 'rb') as f:
        data = pickle.load(f)
        print(f"Timestamp: {data.get('timestamp')}")
        content = data.get('data', {})
        print(f"Total Records: {len(content)}")
        print("Sample 5 records:")
        for k in list(content.keys())[:5]:
            print(f"  {k}: {content[k]}")
else:
    print("Cache not found")
