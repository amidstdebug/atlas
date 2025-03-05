"""
Meeting minutes generation prompts.
This file contains all prompt templates used by the MinutesPipeline class.
"""

# Prompt for identifying topic segments within a meeting transcript
TOPICAL_SEGMENTATION_PROMPT = """
You are analyzing a business meeting transcript to identify natural topical segments.

YOUR TASK:
Identify 2-5 coherent, meaningful topic segments in this transcript that represent distinct discussion topics, agenda items, or conversation themes.

IMPORTANT GUIDELINES:
1. DO NOT simply divide the transcript into equal-sized chunks of 3-4 sentences each
2. Each segment should represent a complete, coherent conversation topic
3. Segments should vary in size depending on how long each topic was discussed
4. Look for natural topic transitions in the conversation
5. Pay attention to keywords, theme changes, and shifts in discussion focus

EXAMPLES OF GOOD SEGMENTATION:
- Product launch discussion (sentences 1-12)
- Budget review (sentences 13-28) 
- Team restructuring (sentences 29-40)

<output_format>
Only respond with segment ranges in this exact format (one per line):
1: [start]-[end]
2: [start]-[end]
3: [start]-[end]

For example:
1: 1-12
2: 13-28
3: 29-40
<output_format/>

<transcript>
{full_text}
<transcript/>
"""

# Prompt for generating a section title from a group of related segments
SECTION_TITLE_PROMPT = """
<instruction>
Create a concise business-appropriate title (5-8 words max) for this meeting segment.
The title should:
- Clearly identify the specific topic or agenda item
- Use professional terminology 
- Be specific and descriptive rather than generic
- Capture the core business function, project, or decision area discussed
- Avoid unnecessary punctuation or filler words

If the conversation is informal or non-business related, still provide a professional-sounding title that captures the essence of the topic without commentary on its relevance.
<instruction/>

<conversation>
{window_text}
<conversation/>
"""

# Prompt for generating a structured summary for a section
SECTION_SUMMARY_PROMPT = """
<instructions>
Create a professional meeting minutes summary from this conversation segment. Extract only the substantive information that would be relevant in a business context.

IMPORTANT: 
- Include ONLY information that was actually discussed - do not add disclaimers about missing information
- Skip any category that has no relevant content (don't include empty categories)
- Do not make meta-comments about the quality or relevance of the conversation
- Do not include headings like "Meeting Minutes Summary" or decorative dividers
- Avoid phrases like "based on the provided conversation" or "in this segment"
- Keep your summary direct, concise, and factual

Extract actionable business information in these categories:

<categories>
1. Key Discussion Points:
   - Identify the main topics actually discussed
   - Extract specific facts, figures, and data points mentioned
   - Capture essential context and background information

2. Decisions Made:
   - Document any formal or informal decisions reached
   - Note approvals, rejections, or consensus points
   - Include rationale for decisions when mentioned

3. Action Items:
   - List specific tasks assigned to individuals
   - Include deadlines and priority levels mentioned
   - Note any required follow-up or dependencies

4. Open Issues:
   - Identify unresolved questions or concerns
   - Document items explicitly deferred to future meetings
   - Note any disagreements or points requiring further discussion
<categories/>

<output_format>
- Begin with the most relevant category that has content
- Use bullet points for clarity
- Be concise yet comprehensive
- Maintain a professional, objective tone
- Focus on facts rather than opinions
- Ensure each point is clear and actionable where applicable
- ONLY include categories where relevant content exists
<output_format/>
<instructions/>

<conversation>
{segments_text}
<conversation/>
"""