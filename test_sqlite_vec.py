import sqlite3
import os

def check():
    conn = sqlite3.connect(':memory:')
    conn.enable_load_extension(True)
    
    # Try common locations/names for the extension
    extensions = ['sqlite_vec', 'vec0']
    found = False
    for ext in extensions:
        try:
            conn.load_extension(ext)
            print(f"SUCCESS: {ext} loaded")
            found = True
            break
        except Exception as e:
            pass
            
    if not found:
        print("FAIL: sqlite-vec extension not found in common paths.")

if __name__ == "__main__":
    check()
