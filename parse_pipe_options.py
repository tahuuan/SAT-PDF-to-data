#!/usr/bin/env python3
"""
Script to parse pipe-separated options back to structured format
"""

def parse_pipe_options(options_text):
    """Convert pipe-separated options back to list of dicts"""
    if options_text == 'NO_OPTIONS' or not options_text:
        return []
    
    options = []
    parts = options_text.split(' | ')
    
    for part in parts:
        if ':' in part:
            value, text = part.split(':', 1)
            options.append({
                'value': value.strip(),
                'text': text.strip()
            })
    
    return options

# Example usage:
if __name__ == "__main__":
    test_options = "A: Option A text | B: Option B text | C: Option C text"
    result = parse_pipe_options(test_options)
    print("Parsed options:", result)
