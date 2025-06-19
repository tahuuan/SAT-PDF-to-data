#!/usr/bin/env python3
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import json
from typing import Dict, List, Optional
import re
from datetime import datetime
import matplotlib
matplotlib.use('TkAgg')
import matplotlib.pyplot as plt
import io
from PIL import Image, ImageTk

class MathRenderer:
    """Class to render LaTeX expressions and tables to images"""
    
    def __init__(self):
        plt.rc('font', **{'family':'serif', 'size': 11})
        self.latex_available = True  
        
        try:
            import tempfile
            import os
            from matplotlib.figure import Figure
            
            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp_file:
                temp_filename = tmp_file.name
            
            try:
                fig = Figure(figsize=(2, 1))
                ax = fig.add_subplot(111)
                test_table = r'\begin{tabular}{|c|}\hline Test \\ \hline\end{tabular}'
                ax.text(0.5, 0.5, test_table, usetex=True, ha='center', va='center')
                ax.axis('off')
                fig.savefig(temp_filename, bbox_inches='tight')
                
                self.usetex_available = True
                print("✅ LaTeX usetex available for table rendering")
                
            finally:
                try:
                    os.unlink(temp_filename)
                except:
                    pass
                    
        except Exception as e:
            self.usetex_available = False
            print(f"❌ LaTeX usetex not available: {str(e)[:50]}...")
            print("   Using matplotlib table fallback")
        

        
    def parse_and_convert_math(self, text):
        """Parse text and convert math expressions and tables"""
        inline_pattern = r'\\?\\\((.*?)\\?\\\)'
        display_pattern = r'\\?\\\[(.*?)\\?\\\]'
        
        table_pattern = r'\\begin\{tabular\}.*?\\end\{tabular\}'
        
        def replace_table(match):
            table_code = match.group(0)
            return f"[TABLE]{table_code}[/TABLE]"
        
        text = re.sub(table_pattern, replace_table, text, flags=re.DOTALL)
        
        def replace_math(match):
            latex_expr = match.group(1)
            
            if self.latex_available:
                return f"[MATH]{latex_expr}[/MATH]"
            else:
                return self.simplify_latex(latex_expr)
        
        text = re.sub(inline_pattern, replace_math, text)
        text = re.sub(display_pattern, replace_math, text)
        
        return text
    
    def extract_math_expressions(self, text):
        """Extract math expressions from text to render separately"""
        math_pattern = r'\[MATH\](.*?)\[/MATH\]'
        expressions = re.findall(math_pattern, text)
        return expressions
    
    def replace_math_with_placeholder(self, text, placeholder="[MATH_IMAGE]"):
        """Replace math expressions with placeholder to insert image after"""
        math_pattern = r'\[MATH\](.*?)\[/MATH\]'
        return re.sub(math_pattern, placeholder, text)
    
    def simplify_latex(self, latex_expr):
        """Fallback text when math images are not used"""
        return latex_expr.strip()
    
    def convert_table_to_text(self, table_code):
        """Convert LaTeX table to plain text representation"""
        try:
            lines = table_code.split('\\\\')
            text_rows = []
            
            for line in lines:
                line = re.sub(r'\\hline', '', line)
                line = re.sub(r'\\begin\{tabular\}.*?\}', '', line)
                line = re.sub(r'\\end\{tabular\}', '', line)
                line = line.strip()
                
                if line and '&' in line:
                    cols = [col.strip() for col in line.split('&')]
                    text_rows.append(' | '.join(cols))
            
            if text_rows:
                return '\n'.join(text_rows)
            else:
                return '[Table]'
        except:
            return '[Table]'
    
    def parse_latex_table(self, table_code):
        """Parse LaTeX table code and extract data for matplotlib table"""
        try:
            lines = table_code.split('\\\\')
            table_data = []
            
            for line in lines:
                line = re.sub(r'\\hline', '', line)
                line = re.sub(r'\\begin\{tabular\}.*?\}', '', line)
                line = re.sub(r'\\end\{tabular\}', '', line)
                line = line.strip()
                
                if line and '&' in line:
                    cols = [col.strip() for col in line.split('&')]
                    table_data.append(cols)
            
            return table_data
        except:
            return []
    


    def render_latex_to_image(self, latex_expr):
        """Render LaTeX expression or table to PIL Image"""
        try:
            is_table = latex_expr.strip().startswith('\\begin{tabular}')
            
            if is_table and self.usetex_available:
                return self.render_table_with_usetex(latex_expr)
            elif is_table:
                return self.render_table_with_matplotlib(latex_expr)
            else:
                return self.render_math_expression(latex_expr)
            
        except Exception as e:
            print(f"Error rendering LaTeX: {e}")
            return None
    
    def render_table_with_usetex(self, table_code):
        """Render table using usetex (most reliable method)"""
        try:
            import tempfile
            import os
            from matplotlib.figure import Figure
            
            # Create temporary file
            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp_file:
                temp_filename = tmp_file.name
            
            try:
                fig = Figure(figsize=(4, 2))
                ax = fig.add_subplot(111)
                ax.text(0.5, 0.5, table_code, usetex=True, ha='center', va='center', fontsize=11)
                ax.axis('off')
                
                # Save to temporary file
                fig.savefig(temp_filename, bbox_inches='tight', pad_inches=0.1, 
                           facecolor='white', edgecolor='none', dpi=150)
                
                # Load image from file
                pil_image = Image.open(temp_filename)
                
                # Crop whitespace
                pil_image = self.crop_whitespace(pil_image)
                
                return pil_image
                
            finally:
                # Clean up temporary file
                try:
                    os.unlink(temp_filename)
                except:
                    pass
                    
        except Exception as e:
            print(f"Error rendering table with usetex: {e}")
            return None
    
    def render_table_with_matplotlib(self, table_code):
        """Fallback: render table using matplotlib table"""
        try:
            table_data = self.parse_latex_table(table_code)
            
            if not table_data:
                return None
                
            # Create matplotlib table
            fig, ax = plt.subplots(figsize=(1.0, 0.6))
            ax.axis('off')
            
            table = ax.table(cellText=table_data,
                           cellLoc='center',
                           loc='center',
                           colWidths=[0.15] * len(table_data[0]))
            
            # Style the table
            table.auto_set_font_size(False)
            table.set_fontsize(10)
            table.scale(1.2, 1.5)
            
            # Style cells
            for (row, col), cell in table.get_celld().items():
                if row == 0:  # Header row
                    cell.set_text_props(weight='bold')
                    cell.set_facecolor('#E6E6FA')
                else:
                    cell.set_facecolor('#F8F8FF')
                cell.set_edgecolor('#000000')
                cell.set_linewidth(1)
            
            # Save to buffer
            buffer = io.BytesIO()
            plt.savefig(buffer, format='png', dpi=120, bbox_inches='tight', 
                       facecolor='white', edgecolor='none', pad_inches=0.05)
            buffer.seek(0)
            
            pil_image = Image.open(buffer)
            pil_image = self.crop_whitespace(pil_image)
            
            plt.close(fig)
            return pil_image
            
        except Exception as e:
            print(f"Error rendering table with matplotlib: {e}")
            return None
    
    def render_math_expression(self, latex_expr):
        """Render regular math expression"""
        try:
            fig, ax = plt.subplots(figsize=(0.1, 0.1))
            ax.axis('off')
            
            fig.subplots_adjust(left=0, right=1, top=1, bottom=0, wspace=0, hspace=0)
            ax.set_position([0, 0, 1, 1])
            ax.margins(0)
            
            text_obj = ax.text(0.5, 0.5, f'${latex_expr}$', transform=ax.transAxes,
                              fontsize=11, ha='center', va='center')
            
            buffer = io.BytesIO()
            fig.canvas.draw()
            plt.savefig(buffer, format='png', dpi=120, bbox_inches='tight', 
                       facecolor='white', edgecolor='none', pad_inches=0,
                       bbox_extra_artists=[text_obj])
            buffer.seek(0)
            
            pil_image = Image.open(buffer)
            pil_image = self.crop_whitespace(pil_image)
            
            plt.close(fig)
            return pil_image
            
        except Exception as e:
            print(f"Error rendering math expression: {e}")
            return None
    
    def crop_whitespace(self, image):
        """Crop extra whitespace from image to tightly fit content"""
        try:
            if image.mode != 'RGB':
                image = image.convert('RGB')
                
            width, height = image.size
            
            left = 0
            right = width - 1
            top = 0
            bottom = height - 1
            
            for x in range(width):
                has_content = False
                for y in range(height):
                    pixel = image.getpixel((x, y))
                    if not (pixel[0] >= 248 and pixel[1] >= 248 and pixel[2] >= 248):
                        has_content = True
                        break
                if has_content:
                    left = x
                    break
            
            # Scan from right to find last non-white column
            for x in range(width - 1, -1, -1):
                has_content = False
                for y in range(height):
                    pixel = image.getpixel((x, y))
                    if not (pixel[0] >= 248 and pixel[1] >= 248 and pixel[2] >= 248):
                        has_content = True
                        break
                if has_content:
                    right = x
                    break
            
            # Scan from top to find first non-white row
            for y in range(height):
                has_content = False
                for x in range(width):
                    pixel = image.getpixel((x, y))
                    if not (pixel[0] >= 248 and pixel[1] >= 248 and pixel[2] >= 248):
                        has_content = True
                        break
                if has_content:
                    top = y
                    break
            
            for y in range(height - 1, -1, -1):
                has_content = False
                for x in range(width):
                    pixel = image.getpixel((x, y))
                    if not (pixel[0] >= 248 and pixel[1] >= 248 and pixel[2] >= 248):
                        has_content = True
                        break
                if has_content:
                    bottom = y
                    break
            
            if left >= right or top >= bottom:
                return image
            
            # Add minimal margin (just 1 pixel)
            left = max(0, left - 1)
            top = max(0, top - 1)
            right = min(width - 1, right + 1)
            bottom = min(height - 1, bottom + 1)
            
            cropped = image.crop((left, top, right + 1, bottom + 1))
            return cropped
            
        except Exception as e:
            print(f"Error cropping image: {e}")
            return image
    
    def render_math_to_tk_image(self, latex_expr):
        """Render LaTeX and convert to Tkinter PhotoImage"""
        pil_image = self.render_latex_to_image(latex_expr)
        if pil_image:
            return ImageTk.PhotoImage(pil_image)
        return None

class SATQuestionViewer:
    def __init__(self, root):
        self.root = root
        self.root.title("📚 SAT Interactive Quiz")
        self.root.geometry("1400x900")
        self.root.configure(bg='#ffffff')
        
        # Math renderer
        self.math_renderer = MathRenderer()
        
        # Math images storage (to prevent garbage collection)
        self.math_images = []
        
        # Math rendering preference
        self.use_math_images = tk.BooleanVar(value=True)
        
        # Data
        self.questions = []
        self.filtered_questions = []
        self.current_question_index = 0
        self.metadata = {}
        
        # Quiz state
        self.user_answer = tk.StringVar()
        self.has_answered = False
        self.score = 0
        self.total_attempted = 0
        self.answered_questions = set()
        
        # Variables
        self.search_var = tk.StringVar()
        self.filter_type_var = tk.StringVar(value="All")
        self.filter_domain_var = tk.StringVar(value="All")
        
        # Setup UI
        self.setup_ui()
        
        # Load default data
        self.load_default_data()
        
    def setup_ui(self):
        """Setup user interface"""
        
        # Main frame
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Configure grid weights
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(2, weight=1)
        
        # Title and Score
        title_frame = ttk.Frame(main_frame)
        title_frame.grid(row=0, column=0, columnspan=3, pady=(0, 10), sticky=(tk.W, tk.E))
        title_frame.columnconfigure(1, weight=1)
        
        title_label = ttk.Label(title_frame, text="📚 SAT Interactive Quiz", 
                               font=('Arial', 18, 'bold'), foreground='#2c3e50')
        title_label.grid(row=0, column=0, sticky=tk.W)
        
        self.score_label = ttk.Label(title_frame, text="Score: 0/0 (0%)", 
                                    font=('Arial', 14, 'bold'), foreground='#27ae60')
        self.score_label.grid(row=0, column=2, sticky=tk.E)
        
        # Control panel
        self.setup_control_panel(main_frame)
        
        # Question content area
        self.setup_question_area(main_frame)
        
        # Navigation panel
        self.setup_navigation_panel(main_frame)
        
        # Status bar
        self.setup_status_bar(main_frame)
        
    def setup_control_panel(self, parent):
        """Setup control panel"""
        control_frame = ttk.LabelFrame(parent, text="🔧 Controls", padding="10")
        control_frame.grid(row=1, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 10))
        
        # Load file button
        ttk.Button(control_frame, text="📁 Load JSON File", 
                  command=self.load_file).grid(row=0, column=0, padx=(0, 10))
        
        # Search
        ttk.Label(control_frame, text="🔍 Search:").grid(row=0, column=1, padx=(10, 5))
        search_entry = ttk.Entry(control_frame, textvariable=self.search_var, width=30)
        search_entry.grid(row=0, column=2, padx=(0, 10))
        search_entry.bind('<KeyRelease>', self.on_search)
        
        # Filter by type
        ttk.Label(control_frame, text="📋 Type:").grid(row=0, column=3, padx=(10, 5))
        type_combo = ttk.Combobox(control_frame, textvariable=self.filter_type_var, 
                                 values=["All"], state="readonly", width=15)
        type_combo.grid(row=0, column=4, padx=(0, 10))
        type_combo.bind('<<ComboboxSelected>>', self.on_filter_change)
        
        # Filter by domain
        ttk.Label(control_frame, text="🎯 Domain:").grid(row=0, column=5, padx=(10, 5))
        domain_combo = ttk.Combobox(control_frame, textvariable=self.filter_domain_var, 
                                   values=["All"], state="readonly", width=15)
        domain_combo.grid(row=0, column=6, padx=(0, 10))
        domain_combo.bind('<<ComboboxSelected>>', self.on_filter_change)
        
        # Statistics button
        ttk.Button(control_frame, text="📊 Statistics", 
                  command=self.show_statistics).grid(row=0, column=7, padx=(10, 0))
                  
        # Reset quiz button
        ttk.Button(control_frame, text="🔄 Reset Quiz", 
                  command=self.reset_quiz).grid(row=0, column=8, padx=(10, 0))
                  
        # Math display toggle
        math_toggle = ttk.Checkbutton(control_frame, text="🔢 Math Images", 
                                     variable=self.use_math_images, 
                                     command=self.on_math_display_toggle)
        math_toggle.grid(row=0, column=9, padx=(10, 0))
        
        self.type_combo = type_combo
        self.domain_combo = domain_combo
        
    def setup_question_area(self, parent):
        """Set up question display area"""
        question_frame = ttk.LabelFrame(parent, text="❓ Interactive Quiz", padding="15")
        question_frame.grid(row=2, column=0, columnspan=3, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))
        question_frame.columnconfigure(0, weight=1)
        question_frame.rowconfigure(2, weight=1)
        
        # Question info bar
        info_frame = ttk.Frame(question_frame)
        info_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 15))
        info_frame.columnconfigure(2, weight=1)
        
        self.question_id_label = ttk.Label(info_frame, text="ID: ", font=('Arial', 12, 'bold'), foreground='#2c3e50')
        self.question_id_label.grid(row=0, column=0, sticky=tk.W)
        
        self.question_type_label = ttk.Label(info_frame, text="Type: ", font=('Arial', 10), foreground='#34495e')
        self.question_type_label.grid(row=0, column=1, padx=(20, 0), sticky=tk.W)
        
        self.question_source_label = ttk.Label(info_frame, text="Source: ", font=('Arial', 10), foreground='#7f8c8d')
        self.question_source_label.grid(row=0, column=2, sticky=tk.E)
        
        # Question text area
        question_text_frame = ttk.Frame(question_frame)
        question_text_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 15))
        question_text_frame.columnconfigure(0, weight=1)
        question_text_frame.rowconfigure(0, weight=1)
        
        self.question_text = tk.Text(question_text_frame, wrap=tk.WORD, height=8, 
                                    font=('Arial', 12), padx=15, pady=15, 
                                    bg='#f8f9fa', relief='flat', bd=1)
        question_scrollbar = ttk.Scrollbar(question_text_frame, orient=tk.VERTICAL, command=self.question_text.yview)
        self.question_text.configure(yscrollcommand=question_scrollbar.set)
        
        self.question_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        question_scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        
        # Options and answer area
        answer_frame = ttk.LabelFrame(question_frame, text="📝 Choose Your Answer", padding="15")
        answer_frame.grid(row=2, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 15))
        answer_frame.columnconfigure(0, weight=1)
        
        # Radio buttons for options
        self.option_buttons = []
        self.option_frames = []
        
        for i, option_id in enumerate(['A', 'B', 'C', 'D']):
            option_frame = ttk.Frame(answer_frame)
            option_frame.grid(row=i, column=0, sticky=(tk.W, tk.E), pady=5, padx=10)
            option_frame.columnconfigure(1, weight=1)
            
            radio_btn = ttk.Radiobutton(option_frame, text="", variable=self.user_answer, 
                                       value=option_id, command=self.on_answer_selected,
                                       style='Custom.TRadiobutton')
            radio_btn.grid(row=0, column=0, sticky=tk.W, padx=(0, 10))
            
            # Use Text widget instead of Label to support math images
            option_text = tk.Text(option_frame, height=2, wrap=tk.WORD, 
                                 font=('Arial', 11, 'normal'), 
                                 bg='#ffffff', relief='flat', bd=0,
                                 cursor='arrow', state='disabled')
            option_text.grid(row=0, column=1, sticky=(tk.W, tk.E), pady=2)
            
            self.option_buttons.append(radio_btn)
            self.option_frames.append((option_frame, option_text))
        
        # Submit and result area
        submit_frame = ttk.Frame(answer_frame)
        submit_frame.grid(row=4, column=0, sticky=(tk.W, tk.E), pady=(15, 5))
        submit_frame.columnconfigure(1, weight=1)
        
        self.submit_btn = ttk.Button(submit_frame, text="✅ Submit Answer", 
                                    command=self.submit_answer, style='Accent.TButton')
        self.submit_btn.grid(row=0, column=0, padx=(0, 10))
        
        self.result_label = ttk.Label(submit_frame, text="", font=('Arial', 12, 'bold'))
        self.result_label.grid(row=0, column=1, sticky=tk.W)
        
        # Next question button
        self.next_btn = ttk.Button(submit_frame, text="Next Question ⏩", 
                                  command=self.next_question_quiz, state='disabled')
        self.next_btn.grid(row=0, column=2, padx=(10, 0))
        
        # Explanation area
        self.explanation_frame = ttk.LabelFrame(question_frame, text="💡 Explanation", padding="15")
        self.explanation_text = tk.Text(self.explanation_frame, wrap=tk.WORD, height=4, 
                                       font=('Arial', 11), padx=15, pady=10, 
                                       bg='#f0f8ff', relief='flat', bd=1)
        self.explanation_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        self.explanation_frame.columnconfigure(0, weight=1)
        self.explanation_frame.rowconfigure(0, weight=1)
        
        # Configure text tags for styling
        self.question_text.tag_configure("question", font=('Arial', 13, 'bold'), foreground='#2c3e50')
        self.question_text.tag_configure("figure", font=('Arial', 11, 'italic'), foreground='#e74c3c')
        
        # Configure explanation text tags
        self.explanation_text.tag_configure("explanation", font=('Arial', 11, 'normal'), foreground='#34495e')
        
    def setup_navigation_panel(self, parent):
        """Set up navigation panel"""
        nav_frame = ttk.LabelFrame(parent, text="🧭 Navigation", padding="10")
        nav_frame.grid(row=3, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 10))
        
        # Navigation buttons
        ttk.Button(nav_frame, text="⏮️ First", 
                  command=self.go_to_first).grid(row=0, column=0, padx=(0, 5))
        ttk.Button(nav_frame, text="⏪ Previous", 
                  command=self.go_to_previous).grid(row=0, column=1, padx=5)
        
        self.position_label = ttk.Label(nav_frame, text="0 / 0", font=('Arial', 10, 'bold'))
        self.position_label.grid(row=0, column=2, padx=20)
        
        ttk.Button(nav_frame, text="Next ⏩", 
                  command=self.go_to_next).grid(row=0, column=3, padx=5)
        ttk.Button(nav_frame, text="Last ⏭️", 
                  command=self.go_to_last).grid(row=0, column=4, padx=(5, 0))
        
        # Jump to question
        ttk.Label(nav_frame, text="Go to:").grid(row=0, column=5, padx=(20, 5))
        self.jump_var = tk.StringVar()
        jump_entry = ttk.Entry(nav_frame, textvariable=self.jump_var, width=8)
        jump_entry.grid(row=0, column=6, padx=(0, 5))
        jump_entry.bind('<Return>', self.jump_to_question)
        ttk.Button(nav_frame, text="Go", 
                  command=self.jump_to_question).grid(row=0, column=7)
        
    def setup_status_bar(self, parent):
        """Set up status bar"""
        status_frame = ttk.Frame(parent)
        status_frame.grid(row=4, column=0, columnspan=3, sticky=(tk.W, tk.E))
        status_frame.columnconfigure(1, weight=1)
        
        self.status_label = ttk.Label(status_frame, text="Ready", foreground='#2c3e50')
        self.status_label.grid(row=0, column=0, sticky=tk.W)
        
        self.stats_label = ttk.Label(status_frame, text="", foreground='#7f8c8d')
        self.stats_label.grid(row=0, column=1, sticky=tk.E)
        
    def load_default_data(self):
        """Load default data from questions_with_explanations.json"""
        try:
            with open('questions_with_explanations.json', 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.load_data(data)
                self.status_label.config(text="✅ Loaded questions_with_explanations.json successfully")
        except FileNotFoundError:
            try:
                with open('questions.json', 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.load_data(data)
                    self.status_label.config(text="✅ Loaded questions.json successfully")
            except FileNotFoundError:
                self.status_label.config(text="⚠️ No question files found. Please load a file.")
        except Exception as e:
            self.status_label.config(text=f"❌ Error loading default data: {str(e)}")
            
    def load_file(self):
        """Load JSON file"""
        file_path = filedialog.askopenfilename(
            title="Select JSON file",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        
        if file_path:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.load_data(data)
                    self.status_label.config(text=f"✅ Loaded {file_path} successfully")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to load file:\n{str(e)}")
                self.status_label.config(text=f"❌ Error loading file")
                
    def load_data(self, data: Dict):
        """Load data from dictionary"""
        self.questions = data.get('questions', [])
        self.metadata = data.get('metadata', {})
        
        # Reset quiz state
        self.score = 0
        self.total_attempted = 0
        self.answered_questions.clear()
        
        # Update filter options
        self.update_filter_options()
        
        # Reset filters and apply
        self.search_var.set("")
        self.filter_type_var.set("All")
        self.filter_domain_var.set("All")
        self.apply_filters()
        
        # Go to first question
        self.current_question_index = 0
        self.display_current_question()
        self.update_position_label()
        self.update_stats_label()
        self.update_score_display()
        
    def update_filter_options(self):
        """Update filter options"""
        # Get unique types and domains
        types = set()
        domains = set()
        
        for q in self.questions:
            if q.get('question_type'):
                types.add(q['question_type'])
            if q.get('domain'):
                domains.add(q['domain'])
        
        # Update comboboxes
        type_values = ["All"] + sorted(list(types))
        domain_values = ["All"] + sorted(list(domains))
        
        self.type_combo['values'] = type_values
        self.domain_combo['values'] = domain_values
        
    def apply_filters(self):
        """Apply filters"""
        search_term = self.search_var.get().lower()
        filter_type = self.filter_type_var.get()
        filter_domain = self.filter_domain_var.get()
        
        self.filtered_questions = []
        
        for q in self.questions:
            # Search filter
            if search_term:
                question_text = q.get('question_text', '').lower()
                question_id = q.get('id', '').lower()
                if search_term not in question_text and search_term not in question_id:
                    continue
            
            # Type filter
            if filter_type != "All" and q.get('question_type') != filter_type:
                continue
                
            # Domain filter
            if filter_domain != "All" and q.get('domain') != filter_domain:
                continue
                
            self.filtered_questions.append(q)
        
        # Reset current index if needed
        if self.current_question_index >= len(self.filtered_questions):
            self.current_question_index = 0
            
        self.display_current_question()
        self.update_position_label()
        
    def on_search(self, event=None):
        """Handle search event"""
        self.apply_filters()
        
    def on_filter_change(self, event=None):
        """Handle filter change event"""
        self.apply_filters()
        
    def display_current_question(self):
        """Display current question in quiz mode"""
        self.question_text.config(state=tk.NORMAL)
        self.question_text.delete(1.0, tk.END)
        
        # Reset quiz state
        self.user_answer.set("")
        self.has_answered = False
        self.result_label.config(text="")
        self.submit_btn.config(state='normal')
        self.next_btn.config(state='disabled')
        self.explanation_frame.grid_remove()
        
        if not self.filtered_questions:
            self.question_text.insert(tk.END, "No questions to display.")
            self.question_id_label.config(text="ID: ")
            self.question_type_label.config(text="Type: ")
            self.question_source_label.config(text="Source: ")
            self.question_text.config(state=tk.DISABLED)
            return
            
        if self.current_question_index >= len(self.filtered_questions):
            self.question_text.config(state=tk.DISABLED)
            return
            
        q = self.filtered_questions[self.current_question_index]
        
        # Update info labels
        self.question_id_label.config(text=f"ID: {q.get('id', 'N/A')}")
        self.question_type_label.config(text=f"Type: {q.get('question_type', 'N/A')}")
        self.question_source_label.config(text=f"Source: {q.get('source_file', 'N/A')}")
        
        # Display question text with math rendering
        question_text = q.get('question_text', 'No question text available.')
        
        # Process math expressions
        processed_text = self.math_renderer.parse_and_convert_math(question_text)
        
        # Check if should render math as images
        if self.use_math_images.get() and self.math_renderer.latex_available and '[MATH]' in processed_text:
            self.insert_text_with_math_images(processed_text, "question")
        else:
            # Use Unicode fallback
            if '[MATH]' in processed_text:
                math_exprs = self.math_renderer.extract_math_expressions(processed_text)
                display_text = processed_text
                for expr in math_exprs:
                    unicode_math = self.math_renderer.simplify_latex(expr)
                    display_text = display_text.replace(f'[MATH]{expr}[/MATH]', unicode_math)
                self.question_text.insert(tk.END, display_text, "question")
            else:
                self.question_text.insert(tk.END, processed_text, "question")
        
        # Figure info
        if q.get('has_figure'):
            self.question_text.insert(tk.END, "\n\n📊 [FIGURE] ", "figure")
            if q.get('figure_description'):
                self.question_text.insert(tk.END, f"{q['figure_description']}", "figure")
        
        self.question_text.config(state=tk.DISABLED)
        
        # Update options
        options = q.get('options', [])
        for i, option_id in enumerate(['A', 'B', 'C', 'D']):
            if i < len(options):
                option = options[i]
                option_text = option.get('text', 'No text available')
                
                # Process math in options
                processed_option_text = self.math_renderer.parse_and_convert_math(option_text)
                
                option_frame, option_text_widget = self.option_frames[i]
                
                # Clear and prepare option text widget
                option_text_widget.config(state='normal')
                option_text_widget.delete(1.0, tk.END)
                
                # Insert option ID first
                option_text_widget.insert(tk.END, f"{option_id}. ", "option_id")
                
                # Check if should render math as images
                if self.use_math_images.get() and self.math_renderer.latex_available and '[MATH]' in processed_option_text:
                    self.insert_text_with_math_images(processed_option_text, "option", option_text_widget)
                else:
                    # Use Unicode fallback
                    if '[MATH]' in processed_option_text:
                        math_exprs = self.math_renderer.extract_math_expressions(processed_option_text)
                        display_text = processed_option_text
                        for expr in math_exprs:
                            unicode_math = self.math_renderer.simplify_latex(expr)
                            display_text = display_text.replace(f'[MATH]{expr}[/MATH]', unicode_math)
                        option_text_widget.insert(tk.END, display_text, "option")
                    else:
                        option_text_widget.insert(tk.END, processed_option_text, "option")
                
                # Configure text formatting and disable editing
                option_text_widget.tag_configure("option_id", font=('Arial', 11, 'bold'), foreground='#2c3e50')
                option_text_widget.tag_configure("option", font=('Arial', 11, 'normal'), foreground='#2c3e50')
                option_text_widget.config(state='disabled')
                option_frame.grid()
            else:
                option_frame, option_text_widget = self.option_frames[i]
                option_frame.grid_remove()
                
        # Enable radio buttons
        for btn in self.option_buttons:
            btn.config(state='normal')
            
        # Check if already answered
        question_id = q.get('id', '')
        if question_id in self.answered_questions:
            # Show previous answer
            self.submit_btn.config(state='disabled')
            self.next_btn.config(state='normal')
            self.show_answer_result(q)
            
    def on_answer_selected(self):
        """Handle when user selects an answer"""
        if self.user_answer.get():
            self.submit_btn.config(state='normal')
            
    def submit_answer(self):
        """Handle answer submission"""
        if not self.user_answer.get():
            messagebox.showwarning("No Answer", "Please select an answer before submitting.")
            return
            
        if not self.filtered_questions:
            return
            
        q = self.filtered_questions[self.current_question_index]
        self.has_answered = True
        question_id = q.get('id', '')
        
        # Add to answered questions
        self.answered_questions.add(question_id)
        
        # Check if answer is correct
        correct_answer = q.get('correct_answer', '')
        user_answer = self.user_answer.get()
        
        self.total_attempted += 1
        
        if user_answer == correct_answer:
            self.score += 1
            
        self.show_answer_result(q)
        self.update_score_display()
        
        # Disable submit button and enable next
        self.submit_btn.config(state='disabled')
        self.next_btn.config(state='normal')
        
        # Disable radio buttons
        for btn in self.option_buttons:
            btn.config(state='disabled')
            
    def show_answer_result(self, question):
        """Display answer result"""
        correct_answer = question.get('correct_answer', '')
        user_answer = self.user_answer.get()
        
        # Update option colors
        for i, option_id in enumerate(['A', 'B', 'C', 'D']):
            option_frame, option_text_widget = self.option_frames[i]
            
            if option_id == correct_answer:
                # Highlight correct answer in green
                option_text_widget.tag_configure("option_id", foreground='#27ae60', font=('Arial', 11, 'bold'))
                option_text_widget.tag_configure("option", foreground='#27ae60', font=('Arial', 11, 'bold'))
            elif option_id == user_answer and user_answer != correct_answer:
                # Highlight wrong answer in red
                option_text_widget.tag_configure("option_id", foreground='#e74c3c', font=('Arial', 11, 'bold'))
                option_text_widget.tag_configure("option", foreground='#e74c3c', font=('Arial', 11, 'bold'))
            else:
                option_text_widget.tag_configure("option_id", foreground='#7f8c8d', font=('Arial', 11, 'normal'))
                option_text_widget.tag_configure("option", foreground='#7f8c8d', font=('Arial', 11, 'normal'))
                
        # Show result
        if user_answer == correct_answer:
            self.result_label.config(text="✅ Correct!", foreground='#27ae60')
        else:
            self.result_label.config(text=f"❌ Wrong! Correct answer: {correct_answer}", foreground='#e74c3c')
            
        # Show explanation
        explanation = question.get('explanation', '')
        if explanation:
            # Process math in explanation
            processed_explanation = self.math_renderer.parse_and_convert_math(explanation)
            
            self.explanation_frame.grid(row=3, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(15, 0))
            self.explanation_text.config(state=tk.NORMAL)
            self.explanation_text.delete(1.0, tk.END)
            
            # Render explanation with math images like question and options
            if self.use_math_images.get() and self.math_renderer.latex_available and '[MATH]' in processed_explanation:
                self.insert_text_with_math_images(processed_explanation, "explanation", self.explanation_text)
            else:
                # Use Unicode fallback
                if '[MATH]' in processed_explanation:
                    math_exprs = self.math_renderer.extract_math_expressions(processed_explanation)
                    display_text = processed_explanation
                    for expr in math_exprs:
                        unicode_math = self.math_renderer.simplify_latex(expr)
                        display_text = display_text.replace(f'[MATH]{expr}[/MATH]', unicode_math)
                    self.explanation_text.insert(tk.END, display_text, "explanation")
                else:
                    self.explanation_text.insert(tk.END, processed_explanation, "explanation")
                
            self.explanation_text.config(state=tk.DISABLED)
            
    def next_question_quiz(self):
        """Go to next question in quiz mode"""
        self.go_to_next()
        
    def update_score_display(self):
        """Update score display"""
        if self.total_attempted > 0:
            percentage = (self.score / self.total_attempted) * 100
            self.score_label.config(text=f"Score: {self.score}/{self.total_attempted} ({percentage:.1f}%)")
        else:
            self.score_label.config(text="Score: 0/0 (0%)")
            
    def reset_quiz(self):
        """Reset quiz - clear all results and start over"""
        result = messagebox.askyesno("Reset Quiz", "Are you sure you want to reset the quiz? This will clear all your progress.")
        if result:
            self.score = 0
            self.total_attempted = 0
            self.answered_questions.clear()
            self.update_score_display()
            self.display_current_question()
            self.status_label.config(text="✅ Quiz reset successfully!")
        
    def update_position_label(self):
        """Update position label"""
        if self.filtered_questions:
            current = self.current_question_index + 1
            total = len(self.filtered_questions)
            self.position_label.config(text=f"{current} / {total}")
        else:
            self.position_label.config(text="0 / 0")
            
    def update_stats_label(self):
        """Cập nhật nhãn thống kê"""
        total_questions = len(self.questions)
        filtered_questions = len(self.filtered_questions)
        
        if self.metadata:
            successful_files = self.metadata.get('total_files_successful', 0)
            failed_files = self.metadata.get('total_files_failed', 0)
            self.stats_label.config(text=f"Total: {total_questions} | Filtered: {filtered_questions} | Files: {successful_files}✅ {failed_files}❌")
        else:
            self.stats_label.config(text=f"Total: {total_questions} | Filtered: {filtered_questions}")
    
    def insert_text_with_math_images(self, text, tag=None, text_widget=None):
        """Insert text with math and table images into text widget"""
        if text_widget is None:
            text_widget = self.question_text
            # Clear existing math images for main question
            self.math_images.clear()
            
        # Debug: Check if we're processing tables
        if '[TABLE]' in text:
            print(f"🔍 DEBUG: insert_text_with_math_images processing text with [TABLE] tags")
            print(f"   Math images enabled: {self.use_math_images.get()}")
            print(f"   Text preview: {text[:100]}...")
        
        # Skip if math images disabled
        if not self.use_math_images.get():
            print("🔍 DEBUG: Math images disabled - using text fallback")
            fallback_text = re.sub(r'\[MATH\](.*?)\[/MATH\]', r'[\1]', text)
            fallback_text = re.sub(r'\[TABLE\](.*?)\[/TABLE\]', 
                                 lambda m: "\n" + self.math_renderer.convert_table_to_text(m.group(1)) + "\n", 
                                 fallback_text, flags=re.DOTALL)
            text_widget.insert(tk.END, fallback_text, tag)
            return
        
        # Process text with math and table rendering
        math_pattern = r'\[MATH\](.*?)\[/MATH\]'
        table_pattern = r'\[TABLE\](.*?)\[/TABLE\]'
        
        # Combine patterns to process in order of appearance  
        combined_pattern = r'(\[MATH\](.*?)\[/MATH\])|(\[TABLE\](.*?)\[/TABLE\])'
        
        last_end = 0
        matches_found = list(re.finditer(combined_pattern, text, re.DOTALL))
        
        for match in matches_found:
            # Insert text before math/table
            if match.start() > last_end:
                text_widget.insert(tk.END, text[last_end:match.start()], tag)
            
            # Check which pattern matched
            if match.group(1):  # Math pattern matched
                math_expr = match.group(2)
                tk_image = self.math_renderer.render_math_to_tk_image(math_expr)
                
                if tk_image:
                    # Store image reference
                    self.math_images.append(tk_image)
                    # Insert image
                    text_widget.image_create(tk.END, image=tk_image)
                else:
                    # Fallback to LaTeX text
                    text_widget.insert(tk.END, f"[{math_expr}]", tag)
                    
            elif match.group(3):  # Table pattern matched
                table_code = match.group(4)
                print(f"🎨 DEBUG: Rendering table image for: {table_code[:30]}...")
                tk_image = self.math_renderer.render_math_to_tk_image(table_code)
                
                if tk_image:
                    print("✅ DEBUG: Table image rendered successfully!")
                    # Store image reference
                    self.math_images.append(tk_image)
                    # Insert image
                    text_widget.image_create(tk.END, image=tk_image)
                else:
                    print("❌ DEBUG: Table image failed, using text fallback")
                    # Fallback to text table
                    fallback_table = self.math_renderer.convert_table_to_text(table_code)
                    text_widget.insert(tk.END, "\n" + fallback_table + "\n", tag)
            
            last_end = match.end()
        
        # Insert remaining text
        if last_end < len(text):
            text_widget.insert(tk.END, text[last_end:], tag)
    
    def on_math_display_toggle(self):
        """Handle math display toggle"""
        self.display_current_question()
    
    def go_to_first(self):
        """Đi đến câu hỏi đầu tiên"""
        if self.filtered_questions:
            self.current_question_index = 0
            self.display_current_question()
            self.update_position_label()
    
    def go_to_previous(self):
        """Đi đến câu hỏi trước"""
        if self.filtered_questions and self.current_question_index > 0:
            self.current_question_index -= 1
            self.display_current_question()
            self.update_position_label()
    
    def go_to_next(self):
        """Đi đến câu hỏi tiếp theo"""
        if self.filtered_questions and self.current_question_index < len(self.filtered_questions) - 1:
            self.current_question_index += 1
            self.display_current_question()
            self.update_position_label()
    
    def go_to_last(self):
        """Đi đến câu hỏi cuối cùng"""
        if self.filtered_questions:
            self.current_question_index = len(self.filtered_questions) - 1
            self.display_current_question()
            self.update_position_label()
    
    def jump_to_question(self, event=None):
        """Nhảy đến câu hỏi theo số thứ tự"""
        try:
            position = int(self.jump_var.get())
            if 1 <= position <= len(self.filtered_questions):
                self.current_question_index = position - 1
                self.display_current_question()
                self.update_position_label()
                self.jump_var.set("")
            else:
                messagebox.showwarning("Invalid Position", 
                                     f"Please enter a number between 1 and {len(self.filtered_questions)}")
        except ValueError:
            messagebox.showwarning("Invalid Input", "Please enter a valid number")
    
    def show_statistics(self):
        """Display statistics"""
        if not self.questions:
            messagebox.showinfo("Statistics", "No data loaded.")
            return
            
        # Calculate statistics
        total_questions = len(self.questions)
        
        # Count by type
        type_counts = {}
        domain_counts = {}
        complete_count = 0
        has_figure_count = 0
        has_answer_count = 0
        
        for q in self.questions:
            # Type
            q_type = q.get('question_type', 'Unknown') or 'Unknown'
            type_counts[q_type] = type_counts.get(q_type, 0) + 1
            
            # Domain
            domain = q.get('domain', 'Unknown') or 'Unknown'
            domain_counts[domain] = domain_counts.get(domain, 0) + 1
            
            # Completeness
            if q.get('is_complete', False):
                complete_count += 1
                
            # Figures
            if q.get('has_figure', False):
                has_figure_count += 1
                
            # Answers
            if q.get('correct_answer'):
                has_answer_count += 1
        
        # Create statistics window
        stats_window = tk.Toplevel(self.root)
        stats_window.title("📊 Statistics")
        stats_window.geometry("500x600")
        stats_window.configure(bg='#f0f0f0')
        
        # Create scrollable text
        text_frame = ttk.Frame(stats_window, padding="10")
        text_frame.pack(fill=tk.BOTH, expand=True)
        
        stats_text = tk.Text(text_frame, wrap=tk.WORD, font=('Arial', 10))
        scrollbar = ttk.Scrollbar(text_frame, orient=tk.VERTICAL, command=stats_text.yview)
        stats_text.configure(yscrollcommand=scrollbar.set)
        
        stats_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Add statistics content
        stats_content = f"""📊 SAT Questions Statistics

🔢 General Statistics:
• Total Questions: {total_questions}
• Complete Questions: {complete_count} ({complete_count/total_questions*100:.1f}%)
• Questions with Figures: {has_figure_count} ({has_figure_count/total_questions*100:.1f}%)
• Questions with Answers: {has_answer_count} ({has_answer_count/total_questions*100:.1f}%)

📋 Question Types:
"""
        for q_type, count in sorted(type_counts.items()):
            percentage = count/total_questions*100
            stats_content += f"• {q_type}: {count} ({percentage:.1f}%)\n"
            
        stats_content += f"\n🎯 Domains:\n"
        for domain, count in sorted(domain_counts.items()):
            percentage = count/total_questions*100
            stats_content += f"• {domain}: {count} ({percentage:.1f}%)\n"
        
        # Add metadata if available
        if self.metadata:
            stats_content += f"\n📁 File Information:\n"
            stats_content += f"• Extraction Date: {self.metadata.get('extraction_date', 'N/A')}\n"
            stats_content += f"• Model Used: {self.metadata.get('model_used', 'N/A')}\n"
            stats_content += f"• Files Processed: {self.metadata.get('total_files_processed', 0)}\n"
            stats_content += f"• Successful Files: {self.metadata.get('total_files_successful', 0)}\n"
            stats_content += f"• Failed Files: {self.metadata.get('total_files_failed', 0)}\n"
            
            if self.metadata.get('successful_files'):
                stats_content += f"\n✅ Successful Files:\n"
                for file in self.metadata['successful_files']:
                    stats_content += f"• {file}\n"
                    
            if self.metadata.get('failed_files'):
                stats_content += f"\n❌ Failed Files:\n"
                for file in self.metadata['failed_files']:
                    stats_content += f"• {file}\n"
        
        stats_text.insert(tk.END, stats_content)
        stats_text.config(state=tk.DISABLED)

def main():
    """Main function"""
    root = tk.Tk()
    app = SATQuestionViewer(root)
    
    # Keyboard shortcuts
    root.bind('<Left>', lambda e: app.go_to_previous())
    root.bind('<Right>', lambda e: app.go_to_next())
    root.bind('<Home>', lambda e: app.go_to_first())
    root.bind('<End>', lambda e: app.go_to_last())
    root.bind('<Control-o>', lambda e: app.load_file())
    root.bind('<F5>', lambda e: app.show_statistics())
    
    root.mainloop()

if __name__ == "__main__":
    main() 