def _replace_image_tags_with_images(self, content: str, images: List[Dict]) -> str:
    """Replace [IMAGE_{page}_{index}_ANALYSIS]...[END_IMAGE_{page}_{index}_ANALYSIS] with <img>"""
    import re
    
    # Create image lookup by (page, index)
    image_lookup = {(img['page'], img['image_index']): img for img in images}
    
    # ✅ CORRECTED REGEX: Matches [IMAGE_1_1_ANALYSIS]...[END_IMAGE_1_1_ANALYSIS]
    pattern = r'\[IMAGE_(\d+)_(\d+)_ANALYSIS\](.*?)\[END_IMAGE_\1_\2_ANALYSIS\]'
    
    def create_image_replacement(match):
        page_num = int(match.group(1))
        img_index = int(match.group(2))
        
        # Lookup image by (page, index)
        img_data = image_lookup.get((page_num, img_index))
        
        if not img_data:
            return ""  # Remove tag if no matching image
        
        # ✅ Use file_path for src (relative path)
        img_src = img_data['file_path'].replace('\\', '/')
        img_alt = img_data['image_description'].replace('"', '&quot;').replace("'", "&#39;")
        
        # ✅ Simple <img> tag only - no extra divs/metrics
        return f'<img src="{img_src}" alt="{img_alt}" style="max-width:100%; height:auto; border-radius:8px; margin:25px auto; display:block; box-shadow:0 8px 25px rgba(0,0,0,0.15);">'
    
    # Replace ALL matching blocks
    content_with_images = re.sub(pattern, create_image_replacement, content, flags=re.DOTALL)
    
    return content_with_images
