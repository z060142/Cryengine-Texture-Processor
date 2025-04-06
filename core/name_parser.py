#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Texture Name Parser

This module provides functionality for parsing texture filenames to extract
texture type and base name information, handling multi-suffix filenames.
"""

import os
import re
from .texture_analyzer import TextureAnalyzer

class TextureNameParser:
    """
    Class for parsing texture filenames to determine texture type and base name.
    """
    
    def __init__(self):
        """
        Initialize the texture name parser with known suffix patterns.
        """
        self.load_default_patterns()
        self.texture_analyzer = TextureAnalyzer()
        # Initialize removable suffixes with defaults, will be updated later if settings exist
        self.removable_suffixes = ["2k", "4k", "8k", "dx", "gl", "directx", "opengl"]
        
    def load_default_patterns(self):
        """
        Load default suffix patterns for texture classification.
        """
        # Patterns for different texture types, ordered by priority
        self.patterns = {
            # Diffuse patterns
            "diffuse": [
                r"_diff(?:use)?(?:_?\d+k)?$",
                r"_col(?:or)?(?:_?\d+k)?$",
                r"_albedo(?:_?\d+k)?$",
                r"_basecolor(?:_?\d+k)?$",
                r"_base[\-_]?col(?:or)?(?:_?\d+k)?$",
                r"_d(?:_?\d+k)?$"
            ],
            
            # Normal map patterns
            "normal": [
                r"_norm(?:al)?(?:_?\d+k)?$",
                r"_n(?:_?\d+k)?$",
                r"_nrm(?:_?\d+k)?$",
                r"_normal[\-_]?(?:directx|dx)(?:_?\d+k)?$", 
                r"_normal[\-_]?(?:opengl|gl)(?:_?\d+k)?$"
            ],
            
            # Specular patterns
            "specular": [
                r"_spec(?:ular)?(?:_?\d+k)?$",
                r"_s(?:_?\d+k)?$",
                r"_refl(?:ection)?(?:_?\d+k)?$"
            ],
            
            # Glossiness patterns
            "glossiness": [
                r"_gloss(?:iness)?(?:_?\d+k)?$",
                r"_glossy(?:_?\d+k)?$",
                r"_g(?:_?\d+k)?$",
                r"_smoothness(?:_?\d+k)?$"
            ],
            
            # Roughness patterns
            "roughness": [
                r"_rough(?:ness)?(?:_?\d+k)?$",
                r"_r(?:_?\d+k)?$"
            ],
            
            # Displacement patterns
            "displacement": [
                r"_disp(?:lacement)?(?:_?\d+k)?$",
                r"_height(?:_?\d+k)?$",
                r"_h(?:_?\d+k)?$",
                r"_bump(?:_?\d+k)?$"
            ],
            
            # Metallic patterns
            "metallic": [
                r"_metal(?:lic)?(?:_?\d+k)?$",
                r"_m(?:_?\d+k)?$"
            ],
            
            # Ambient occlusion patterns
            "ao": [
                r"_ao(?:_?\d+k)?$",
                r"_ambient[\-_]?occlusion(?:_?\d+k)?$",
                r"_occlusion(?:_?\d+k)?$"
            ],
            
            # Alpha/transparency patterns
            "alpha": [
                r"_alpha(?:_?\d+k)?$",
                r"_a(?:_?\d+k)?$",
                r"_opacity(?:_?\d+k)?$",
                r"_transparency(?:_?\d+k)?$"
            ],
            
            # Emissive patterns
            "emissive": [
                r"_emissive(?:_?\d+k)?$",
                r"_emission(?:_?\d+k)?$",
                r"_e(?:_?\d+k)?$",
                r"_glow(?:_?\d+k)?$"
            ],
            
            # Subsurface scattering patterns
            "sss": [
                r"_sss(?:_?\d+k)?$",
                r"_subsurface(?:_?\d+k)?$"
            ],
            
            # ARM combined texture patterns (Ambient Occlusion, Roughness, Metallic)
            "arm": [
                r"_arm(?:_?\d+k)?$",
                r"_a?rm(?:_?\d+k)?$",
                r"_rm?a(?:_?\d+k)?$",
                r"_occlusion[\-_]?roughness[\-_]?metallic(?:_?\d+k)?$",
                r"_ao[\-_]?rough[\-_]?metal(?:_?\d+k)?$"
            ]
        }
        
        # Compile patterns
        self.compile_patterns()
        
    def compile_patterns(self):
        """
        Compile regex patterns for all texture types.
        """
        # Compiled regex patterns
        self.compiled_patterns = {}
        for texture_type, patterns in self.patterns.items():
            self.compiled_patterns[texture_type] = [re.compile(pattern, re.IGNORECASE) for pattern in patterns]
            
    def load_patterns(self, patterns_dict):
        """
        Load custom suffix patterns for texture classification.
        
        Args:
            patterns_dict: Dictionary mapping texture types to lists of suffix patterns
        """
        if not patterns_dict:
            return
            
        # Convert suffix lists to regex patterns
        self.patterns = {}
        for texture_type, suffixes in patterns_dict.items():
            # Handle removable suffixes separately
            if texture_type == "removable_suffixes":
                self.removable_suffixes = [suffix.strip().lower() for suffix in suffixes]
                continue
                
            # Convert simple suffixes to regex patterns
            patterns = []
            for suffix in suffixes:
                # Clean up suffix and escape special regex characters
                suffix = re.escape(suffix.strip())
                # Add pattern for optional resolution suffix
                pattern = f"_{suffix}(?:_?\\d+k)?$"
                patterns.append(pattern)
                
            if patterns:
                self.patterns[texture_type] = patterns
                
        # Add ARM patterns if not present
        if "arm" not in self.patterns:
            self.patterns["arm"] = [
                r"_arm(?:_?\d+k)?$",
                r"_a?rm(?:_?\d+k)?$",
                r"_rm?a(?:_?\d+k)?$",
                r"_occlusion[\-_]?roughness[\-_]?metallic(?:_?\d+k)?$",
                r"_ao[\-_]?rough[\-_]?metal(?:_?\d+k)?$"
            ]
                
        # Recompile patterns
        self.compile_patterns()
    
    def _clean_filename(self, name):
        """
        Clean a filename by removing the specified removable suffixes.
        
        Args:
            name: Filename to clean
            
        Returns:
            Cleaned filename
        """
        name_parts = name.split('_')
        cleaned_parts = []
        
        # Check each part against removable suffixes
        for part in name_parts:
            part_lower = part.lower()
            if part_lower not in self.removable_suffixes:
                cleaned_parts.append(part)
        
        # Rejoin the remaining parts
        return '_'.join(cleaned_parts)
    
    def parse(self, file_path):
        """
        Parse a texture filename to determine its type and base name.
        
        Args:
            file_path: Path to the texture file
            
        Returns:
            Tuple of (texture_type, base_name)
        """
        filename = os.path.basename(file_path)
        name_without_ext = os.path.splitext(filename)[0]
        
        # First clean the filename by removing removable suffixes
        clean_name = self._clean_filename(name_without_ext)
        
        # First check for CryEngine specific suffixes
        cry_patterns = {
            "diffuse": [r"_diff$"],
            "normal": [r"_ddna$"],
            "displacement": [r"_displ$"],
            "specular": [r"_spec$"],
            "emissive": [r"_emissive$"],
            "sss": [r"_sss$"]
        }
        
        for texture_type, patterns in cry_patterns.items():
            for pattern in patterns:
                if re.search(pattern, clean_name, re.IGNORECASE):
                    # First get a preliminary base name by removing the matched suffix
                    match = re.search(pattern, clean_name, re.IGNORECASE)
                    preliminary_base_name = clean_name[:match.start()]
                    # Then use the more thorough extraction method to remove any texture identifiers
                    base_name = self._extract_base_name(preliminary_base_name, texture_type)
                    return texture_type, base_name
        
        # If not a CryEngine pattern, try the regular patterns
        for texture_type, patterns in self.compiled_patterns.items():
            for pattern in patterns:
                match = pattern.search(clean_name)
                if match:
                    # First get a preliminary base name by removing the matched suffix
                    preliminary_base_name = clean_name[:match.start()]
                    # Then use the more thorough extraction method to remove any texture identifiers
                    base_name = self._extract_base_name(preliminary_base_name, texture_type)
                    return texture_type, base_name
        
        # If no pattern matches, try using the texture analyzer
        texture_type, confidence = TextureAnalyzer.analyze_texture_type(file_path)
        
        # Only use analyzer result if confidence is reasonable
        if confidence >= 0.5:
            print(f"Texture analyzer identified {file_path} as {texture_type} (confidence: {confidence:.2f})")
            
            # Use our more thorough method to extract base name
            base_name = self._extract_base_name(clean_name, texture_type)
            return texture_type, base_name
        
        # If analyzer couldn't determine type with confidence, mark as unknown
        return "unknown", clean_name
    
    def _extract_base_name(self, name_without_ext, texture_type):
        """
        Extract base name by removing likely texture type suffixes.
        
        Args:
            name_without_ext: Filename without extension
            texture_type: Identified texture type
            
        Returns:
            Extracted base name
        """
        # Check if we have patterns for this texture type
        if texture_type in self.compiled_patterns:
            # Try each pattern for the texture type
            for pattern in self.compiled_patterns[texture_type]:
                match = pattern.search(name_without_ext)
                if match:
                    # Remove the matched suffix to get the base name
                    return name_without_ext[:match.start()]
        
        # Split the name by underscore and remove parts that match texture type identifiers
        # This is a more thorough approach to remove texture type identifiers regardless of position
        parts = name_without_ext.split('_')
        filtered_parts = []
        
        # Common texture identifiers for each type
        type_identifiers = {
            "diffuse": ["diff", "diffuse", "albedo", "basecolor", "color", "col", "d"],
            "normal": ["normal", "nrm", "norm", "n", "nor"],
            "specular": ["spec", "specular", "s"],
            "glossiness": ["gloss", "glossy", "glossiness", "smoothness", "g"],
            "roughness": ["rough", "roughness", "r"],
            "displacement": ["disp", "displacement", "height", "bump", "h"],
            "metallic": ["metal", "metallic", "metalness", "m"],
            "ao": ["ao", "ambient", "occlusion"],
            "alpha": ["alpha", "opacity", "transparency", "a"],
            "emissive": ["emissive", "emission", "glow", "e"],
            "sss": ["sss", "subsurface"]
        }
        
        # Get the identifiers for the current texture type
        identifiers = type_identifiers.get(texture_type, [])
        
        # Filter out parts that match the texture type identifiers
        for part in parts:
            part_lower = part.lower()
            if part_lower not in identifiers:
                filtered_parts.append(part)
        
        if filtered_parts:
            return "_".join(filtered_parts)
        
        # Common word suffixes to remove if found at the end
        common_suffixes = [
            "_" + texture_type,
            texture_type
        ]
        
        for suffix in common_suffixes:
            if name_without_ext.lower().endswith(suffix.lower()):
                return name_without_ext[:-len(suffix)]
        
        # If couldn't extract base name, return the full name
        return name_without_ext
    
    def extract_resolution(self, filename):
        """
        Extract resolution information from a filename if present.
        
        Args:
            filename: Texture filename
            
        Returns:
            Extracted resolution string or None if not found
        """
        # Look for common resolution patterns like 2k, 4k, 1024, etc.
        resolution_patterns = [
            r'_(\d+k)(?:_|$)',  # matches _2k_ or _4k at the end
            r'_(\d+x\d+)(?:_|$)',  # matches _1024x1024_ or _2048x2048 at the end
            r'_([1-8]k)(?:_|$)'  # specifically matches _1k through _8k
        ]
        
        for pattern in resolution_patterns:
            match = re.search(pattern, filename, re.IGNORECASE)
            if match:
                return match.group(1)
        
        return None
    
    def is_directx_normal(self, filename):
        """
        Check if a normal map is in DirectX format based on filename.
        
        Args:
            filename: Texture filename
            
        Returns:
            True if DirectX format, False otherwise
        """
        directx_patterns = [
            r'_normal[\-_]?directx',
            r'_normal[\-_]?dx',
            r'_directx[\-_]?normal',
            r'_dx[\-_]?normal'
        ]
        
        for pattern in directx_patterns:
            if re.search(pattern, filename, re.IGNORECASE):
                return True
        
        # Check for OpenGL patterns
        if self.is_opengl_normal(filename):
            return False
            
        # Default to DirectX format if not specified, as it's more common
        return True
    
    def is_opengl_normal(self, filename):
        """
        Check if a normal map is in OpenGL format based on filename.
        
        Args:
            filename: Texture filename
            
        Returns:
            True if OpenGL format, False otherwise
        """
        opengl_patterns = [
            r'_normal[\-_]?opengl',
            r'_normal[\-_]?gl',
            r'_opengl[\-_]?normal',
            r'_gl[\-_]?normal'
        ]
        
        for pattern in opengl_patterns:
            if re.search(pattern, filename, re.IGNORECASE):
                return True
        
        return False
