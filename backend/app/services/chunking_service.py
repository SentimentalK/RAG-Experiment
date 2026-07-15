import os
import re
import logging
from typing import Dict, Any, List

# Suppress Hugging Face download warnings
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"

from transformers import AutoTokenizer

logger = logging.getLogger(__name__)

class ChunkingService:
    """
    Service responsible for dividing section texts into chunks conforming to MiniLM limits.
    """
    MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
    TARGET_TOKENS = 180
    MAX_TOKENS = 220
    OVERLAP_TOKENS = 30

    def __init__(self, model_name: str = MODEL_NAME):
        logger.info(f"Initializing ChunkingService with tokenizer for {model_name}...")
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)

    def split_into_sentences(self, text: str) -> List[str]:
        """
        Splits text into sentences using a robust regex that ignores common abbreviations
        (Mr, Mrs, Dr, Ms, St, Esq, etc.) and initials.
        """
        sentence_end = re.compile(
            r'(?<!\bMr\.)(?<!\bMR\.)(?<!\bMrs\.)(?<!\bMRS\.)(?<!\bDr\.)(?<!\bDR\.)'
            r'(?<!\bMs\.)(?<!\bMS\.)(?<!\bSt\.)(?<!\bST\.)(?<!\bEsq\.)(?<!\bESQ\.)'
            r'(?<!\b[A-Z]\.)(?<=[.!?])\s+'
        )
        return [s.strip() for s in sentence_end.split(text) if s.strip()]

    def count_tokens(self, text: str) -> int:
        """
        Counts the number of tokens in the text, including special tokens like [CLS] and [SEP].
        """
        token_ids = self.tokenizer.encode(
            text,
            add_special_tokens=True,
            truncation=False
        )
        return len(token_ids)

    def _split_by_token_window(self, text: str, max_chunk_tokens: int = 200) -> List[str]:
        """
        Force-splits text into blocks by word count such that each block is strictly under max_chunk_tokens.
        """
        words = text.split(" ")
        parts = []
        current_words = []
        
        for word in words:
            current_words.append(word)
            current_text = " ".join(current_words)
            if self.count_tokens(current_text) > max_chunk_tokens:
                if len(current_words) > 1:
                    last_word = current_words.pop()
                    parts.append(" ".join(current_words))
                    current_words = [last_word]
                else:
                    parts.append(" ".join(current_words))
                    current_words = []
                    
        if current_words:
            parts.append(" ".join(current_words))
            
        return parts

    def _split_overlong_sentence(self, sentence: str) -> List[str]:
        """
        Splits an exceptionally long sentence using clause punctuation or token window fallback
        to ensure no segment exceeds MAX_TOKENS.
        """
        # Level 1: Split by clause punctuation (semicolon, colon, em-dash)
        clause_splitter = re.compile(r'(?<=[;:])\s+|—\s*')
        sub_sentences = [s.strip() for s in clause_splitter.split(sentence) if s.strip()]
        
        final_parts = []
        for sub_s in sub_sentences:
            sub_len = self.count_tokens(sub_s)
            if sub_len <= self.MAX_TOKENS:
                final_parts.append(sub_s)
            else:
                # Level 2: Token window force-splitting
                logger.warning(
                    f"Clause still exceeds MAX_TOKENS ({sub_len} > {self.MAX_TOKENS}). "
                    f"Applying token window split."
                )
                # target 200 to be safely under 220 when special tokens are added
                window_parts = self._split_by_token_window(sub_s, max_chunk_tokens=200)
                final_parts.extend(window_parts)
                
        return final_parts

    def chunk_section(self, section: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Splits a single section (story) into chunks based on sentence boundaries,
        target size, maximum size, and overlap configurations.
        """
        text = section.get("text", "")
        if not text.strip():
            return []

        # Split section text into paragraphs, then sentences
        paragraphs = text.split("\n\n")
        all_sentences = []
        
        for para in paragraphs:
            if not para.strip():
                continue
            para_sents = self.split_into_sentences(para)
            for sent in para_sents:
                sent_tokens = self.count_tokens(sent)
                if sent_tokens > self.MAX_TOKENS:
                    logger.warning(
                        f"Overlong sentence detected in section {section.get('section_order')} "
                        f"({sent_tokens} tokens). Splitting."
                    )
                    split_sents = self._split_overlong_sentence(sent)
                    all_sentences.extend(split_sents)
                else:
                    all_sentences.append(sent)

        chunks: List[Dict[str, Any]] = []
        chunk_order = 1
        i = 0
        n = len(all_sentences)
        
        next_overlap_sentences = []

        while i < n:
            current_sentences = []
            
            # Start with overlap sentences from previous chunk
            if next_overlap_sentences:
                current_sentences.extend(next_overlap_sentences)
                overlap_tokens_count = self.count_tokens(" ".join(current_sentences))
            else:
                overlap_tokens_count = 0
                
            j = i
            added_new = False
            
            # Slide window forward adding sentences starting from index i
            while j < n:
                candidate_sentences = current_sentences + [all_sentences[j]]
                candidate_text = " ".join(candidate_sentences)
                candidate_tokens = self.count_tokens(candidate_text)
                
                # Check hard ceiling limits
                if candidate_tokens > self.MAX_TOKENS and added_new:
                    break
                    
                current_sentences.append(all_sentences[j])
                added_new = True
                j += 1
                
                # Check target limit
                current_text = " ".join(current_sentences)
                current_tokens = self.count_tokens(current_text)
                if current_tokens >= self.TARGET_TOKENS:
                    break

            chunk_text = " ".join(current_sentences)
            final_tokens = self.count_tokens(chunk_text)
            
            section_order = section["section_order"]
            section_title = section["title"]
            chunk_id = f"g1661-s{section_order:02d}-c{chunk_order:04d}"
            
            chunks.append({
                "chunk_id": chunk_id,
                "section_order": section_order,
                "section_title": section_title,
                "chunk_order": chunk_order,
                "token_count": final_tokens,
                "overlap_tokens": overlap_tokens_count,
                "text": chunk_text
            })
            
            # Calculate next overlap sentences: accumulate backwards until reaching or exceeding OVERLAP_TOKENS
            overlap_sents = []
            for k in range(len(current_sentences) - 1, 0, -1):
                # Insert at the beginning to maintain correct order of sentences
                overlap_sents.insert(0, current_sentences[k])
                overlap_text = " ".join(overlap_sents)
                overlap_tokens = self.count_tokens(overlap_text)
                if overlap_tokens >= self.OVERLAP_TOKENS:
                    break
                
            next_overlap_sentences = overlap_sents
            i = j
            chunk_order += 1

        return chunks

    def chunk_document(self, sections: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Splits all document sections into chunks.
        """
        all_chunks = []
        for sec in sections:
            all_chunks.extend(self.chunk_section(sec))
        return all_chunks
