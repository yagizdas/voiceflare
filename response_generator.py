"""
AI Response Generator using XAI (Grok) API.
Handles generating contextual responses based on detected speech.
"""

import random
from xai_sdk import Client
from xai_sdk.chat import user, system
from config_loader import Config, PromptsConfig


class ResponseGenerator:
    """Generates AI responses using XAI API based on detected keywords."""
    
    def __init__(self, config: Config):
        """
        Initialize response generator.
        
        Args:
            config: Bot configuration containing XAI and prompts settings
        """
        self.config = config
        self.client = Client(
            api_key=config.xai.api_key,
            timeout=config.xai.timeout,
        )
        print("[XAI] Response generator initialized")
    
    def generate_announcement(
        self,
        speaker_name: str,
        target_name: str,
        phrase: str,
        victim_name: str
    ) -> str:
        """
        Generate an announcement/response based on detected speech.
        
        Args:
            speaker_name: Name of the person who spoke
            target_name: Target name associated with the speaker
            phrase: The trigger phrase that was detected
            victim_name: Name of the affected person
            
        Returns:
            Generated announcement text
        """
        # Create declaration prefix
        declaration = f"{speaker_name} said '{phrase}'. "
        
        # Determine which prompt to use based on probability
        use_alternative = random.randint(0, 100) < self.config.prompts.alternative_probability
        
        if use_alternative:
            selected_prompt = self.config.prompts.alternative
        else:
            selected_prompt = self.config.prompts.primary
        
        # Build prompt from template
        initial_context = (
            f"This person: {speaker_name}, "
            f"said something provocative to: {victim_name}."
        )
        
        user_prompt = selected_prompt.user_template.format(
            speaker_name=speaker_name,
            target_name=target_name,
            victim_name=victim_name
        )
        
        # Generate response using XAI
        response_text = self._xai_response(
            prompt=initial_context + " " + user_prompt,
            system_prompt=selected_prompt.system
        )
        
        # Parse and format response
        formatted_response = self._parse_xai_response(response_text, target_name)
        
        # Combine declaration and response
        announcement = declaration + formatted_response
        
        return announcement
    
    def _xai_response(self, prompt: str, system_prompt: str) -> str:
        """
        Get response from XAI API.
        
        Args:
            prompt: User prompt
            system_prompt: System prompt defining behavior
            
        Returns:
            Generated response text
        """
        chat = self.client.chat.create(
            model=self.config.xai.model,
            store_messages=False,
            temperature=self.config.xai.temperature,
            max_tokens=self.config.xai.max_tokens
        )
        
        chat.append(system(system_prompt))
        chat.append(user(prompt))
        response = chat.sample()
        
        return response.content
    
    def _parse_xai_response(self, response: str, target_name: str) -> str:
        """
        Parse and clean XAI response.
        
        Args:
            response: Raw response from XAI
            target_name: Target name to substitute for {target_name} placeholder
            
        Returns:
            Cleaned response text
        """
        # Remove escape characters and substitute placeholders
        cleaned = response.replace("\\", "")
        cleaned = cleaned.replace("{target_name}", target_name)
        cleaned = cleaned.replace("{anne}", target_name)  # Legacy compatibility
        
        return cleaned
