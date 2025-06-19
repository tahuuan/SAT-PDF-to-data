import PyPDF2
import os
import math

def split_pdf(input_file, pages_per_file=10):
    """
    Split PDF file into smaller files
    
    Args:
        input_file: Path to the original PDF file
        pages_per_file: Number of pages per file (default is 10)
    """
    
    # Check if file exists
    if not os.path.exists(input_file):
        print(f"Error: File {input_file} not found")
        return
    
    # Open PDF file
    with open(input_file, 'rb') as file:
        pdf_reader = PyPDF2.PdfReader(file)
        total_pages = len(pdf_reader.pages)
        
        print(f"Original file has {total_pages} pages")
        print(f"Will split into {pages_per_file} pages per file")
        
        # Calculate number of files to be created
        num_files = math.ceil(total_pages / pages_per_file)
        print(f"Will create {num_files} files")
        
        # Create directory to hold the split files
        base_name = os.path.splitext(input_file)[0]
        output_dir = f"{base_name}_split"
        
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
            print(f"Created directory: {output_dir}")
        
        # Split file
        for i in range(num_files):
            start_page = i * pages_per_file
            end_page = min((i + 1) * pages_per_file, total_pages)
            
            # Create new PDF file
            pdf_writer = PyPDF2.PdfWriter()
            
            # Add pages to new file
            for page_num in range(start_page, end_page):
                pdf_writer.add_page(pdf_reader.pages[page_num])
            
            # New file name
            output_filename = f"{base_name}_part{i+1:02d}_pages{start_page+1}-{end_page}.pdf"
            output_path = os.path.join(output_dir, os.path.basename(output_filename))
            
            # Write file
            with open(output_path, 'wb') as output_file:
                pdf_writer.write(output_file)
            
            print(f"Created: {output_path} (pages {start_page+1}-{end_page})")
        
        print(f"\nDone! Files saved in directory: {output_dir}")

if __name__ == "__main__":
    # Name of the PDF file to split
    input_file = "Questions - Test 9.pdf"
    
    # Split file with 10 pages per file
    split_pdf(input_file, pages_per_file=10)