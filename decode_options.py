#!/usr/bin/env python3
"""
Script to decode options_json back to JSON format
"""
import json

def decode_options_json(encoded_str):
    """Convert encoded string back to JSON"""
    if encoded_str == 'EMPTY_ARRAY':
        return []
    
    # Reverse the encoding
    decoded = encoded_str.replace('ARRAY_START', '[').replace('ARRAY_END', ']')
    decoded = decoded.replace('OBJ_START', '{').replace('OBJ_END', '}')
    
    try:
        return json.loads(decoded)
    except:
        return []

# Example usage:
if __name__ == "__main__":
    test_encoded = 'ARRAY_STARTOBJ_START"text":"Option A","value":"A"OBJ_ENDARRAY_END'
    result = decode_options_json(test_encoded)
    print("Decoded:", result)
