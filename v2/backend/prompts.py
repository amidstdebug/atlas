"""
XML Prompt templates for the Meeting Minutes Generator

This module contains functions that generate XML-structured prompts
for different stages of the meeting minutes generation pipeline.
"""
from typing import List, Dict, Any, Tuple

def topic_identification_prompt(batch: List[Tuple], topics: List[Dict[str, Any]]) -> str:
    """
    Generate XML prompt for topic identification.
    
    Args:
        batch: List of (segment, segment_id) tuples
        topics: List of existing topics in the meeting
        
    Returns:
        Formatted XML prompt string
    """
    # Generate segments text
    segments_text = ""
    for segment, segment_id in batch:
        segments_text += f"""<segment>
        <id>{segment_id}</id>
        <timestamp>{segment.segment.start}</timestamp>
        <speaker>{segment.label}</speaker>
        <text>{segment.text}</text>
    </segment>
    """
    
    # Current state context
    topics_context = ""
    for topic in topics:
        topics_context += f"""<topic>
        <id>{topic.id}</id>
        <name>{topic.name}</name>
        <summary>{topic.summary}</summary>
        <status>{topic.status}</status>
    </topic>
    """
    
    prompt = f"""
<transcript_batch>
    {segments_text}
</transcript_batch>    

<current_topics>
    {topics_context}
</current_topics>
    
<instructions>
    Your high level goal is to identify topics from the transcript.
    
    <transcript_batch> contains a number of transcription segments.
    <current_topics> contains topics that have already been identified.
    
    In your output you should output the current topics as well as either: 
    a) Add on new topics that are sufficiently distinct from existing topics
    b) Add no new topics 
    c) Remove current topics if they are too similar

    Criteria for creating a new topic: 
    1. Discussed for multiple segments
    2. Non-trivial
    3. Sufficiently different from existing topics
    4. Less is more: Fewer meaningful topics are preferred over multiple shallow topics

    Rules for creating a topic ID:
    1. Less than 10 characters
    2. Using letters from the name of the topic
    3. Unique

    <important>
        DO:
        - DO answer ONLY in the format specified in <output_format>
        - DO conclude your response with <|answer_over|>
        
        DO NOT:
        - DO NOT include extraneous delimiters like ```. It is understood that you output XML.
        - DO NOT include any content other than what is specified in <output_format>
        - DO NOT include preambles such as 'Here is the output in the specified format:'
    </important>
</instructions>

<output_format>
<topics>
    <topic>
        <name>[TOPIC_NAME]</name>
        <summary>[BRIEF_SUMMARY]</summary>
        <id>[GENERATED_ID|EXISTING_ID]</id>
    </topic>
</topics>
<|answer_over|>
</output_format>
"""
    return prompt

def generate_segment_analysis_prompt(batch: List[Tuple], topic_mapping: Dict[str, str], context: str) -> str:
    """
    Generate XML prompt for detailed segment analysis.
    
    Args:
        batch: List of (segment, segment_id) tuples
        topic_mapping: Dictionary mapping segment IDs to topic IDs
        context: Context information about existing topics, actions, and decisions
        
    Returns:
        Formatted XML prompt string
    """
    segments_text = ""
    for segment, segment_id in batch:
        segments_text += f"""<segment>
        <id>{segment_id}</id>
        <timestamp>{segment.segment.start}</timestamp>
        <speaker>{segment.label}</speaker>
        <text>{segment.text}</text>
        <topic_id>{topic_mapping.get(segment_id, "unknown")}</topic_id>
    </segment>
    """
    
    prompt = f"""<instructions>
  Analyze these transcript segments to extract:
  1. Key discussion points for each topic
  2. Decisions made with supporting evidence
  3. Action items with assignees and deadlines
  4. Different viewpoints or unresolved issues
  
  For each extracted element:
  - Include who said it and provide direct quotes
  - Assign an evidence strength (STRONG|MODERATE|WEAK)
  - Link to specific segments using their IDs
  - Identify if action items are explicitly assigned or implied
</instructions>

<output_format>
  <segment_analysis>
    <topics>
      <topic>
        <id>[TOPIC_ID]</id>
        <key_points>
          <point>
            <summary>[POINT_SUMMARY]</summary>
            <speaker>[SPEAKER]</speaker>
            <segment_id>[SEGMENT_ID]</segment_id>
            <evidence>[DIRECT_QUOTE]</evidence>
            <evidence_strength>STRONG|MODERATE|WEAK</evidence_strength>
          </point>
          <!-- Additional points -->
        </key_points>
      </topic>
      <!-- Additional topics -->
    </topics>
    
    <decisions>
      <decision>
        <description>[DECISION_DESCRIPTION]</description>
        <decision_makers>
          <person>[PERSON_NAME]</person>
          <!-- Additional people if applicable -->
        </decision_makers>
        <topic_id>[RELATED_TOPIC_ID]</topic_id>
        <segment_id>[SEGMENT_ID]</segment_id>
        <evidence>[DIRECT_QUOTE]</evidence>
        <evidence_strength>STRONG|MODERATE|WEAK</evidence_strength>
      </decision>
      <!-- Additional decisions -->
    </decisions>
    
    <action_items>
      <action>
        <description>[ACTION_DESCRIPTION]</description>
        <assignee>[RESPONSIBLE_PERSON]</assignee>
        <deadline>[DEADLINE_IF_MENTIONED]</deadline>
        <topic_id>[RELATED_TOPIC_ID]</topic_id>
        <segment_id>[SEGMENT_ID]</segment_id>
        <evidence>[DIRECT_QUOTE]</evidence>
        <evidence_strength>STRONG|MODERATE|WEAK</evidence_strength>
        <is_explicit>true|false</is_explicit>
      </action>
      <!-- Additional actions -->
    </action_items>
    
    <unresolved_issues>
      <issue>
        <description>[ISSUE_DESCRIPTION]</description>
        <raised_by>[PERSON_WHO_RAISED_IT]</raised_by>
        <topic_id>[RELATED_TOPIC_ID]</topic_id>
        <segment_id>[SEGMENT_ID]</segment_id>
        <evidence>[DIRECT_QUOTE]</evidence>
      </issue>
      <!-- Additional issues -->
    </unresolved_issues>
  </segment_analysis>
</output_format>

<context>
{context}
</context>

<transcript_segments>
{segments_text}
</transcript_segments>
"""
    return prompt

def generate_action_verification_prompt(potential_actions: List[Dict[str, Any]]) -> str:
    """
    Generate XML prompt for action item verification.
    
    Args:
        potential_actions: List of potential action items to verify
        
    Returns:
        Formatted XML prompt string
    """
    actions_text = ""
    for action in potential_actions:
        actions_text += f"""<action>
        <description>{action['description']}</description>
        <assignee>{action['assignee']}</assignee>
        <deadline>{action['deadline']}</deadline>
        <segment_id>{action['segment_id']}</segment_id>
        <evidence>{action['evidence']}</evidence>
    </action>
    """
    
    prompt = f"""<instructions>
  Verify these potential action items extracted from the transcript.
  For each action:
  
  1. Confirm if it's a genuine action item
  2. Classify it as EXPLICIT (clearly assigned) or IMPLICIT (implied task)
  3. Assess evidence quality as STRONG, MODERATE, or WEAK
  4. Check if assignee and deadline are clearly specified
  
  If an item is not actually an action, mark it as NOT_ACTIONABLE.
</instructions>

<output_format>
  <verified_actions>
    <action>
      <original_description>[ORIGINAL_DESCRIPTION]</original_description>
      <verified_description>[REFINED_DESCRIPTION]</verified_description>
      <assignee>[VERIFIED_ASSIGNEE]</assignee>
      <deadline>[VERIFIED_DEADLINE]</deadline>
      <segment_id>[SEGMENT_ID]</segment_id>
      <classification>EXPLICIT|IMPLICIT|NOT_ACTIONABLE</classification>
      <evidence_strength>STRONG|MODERATE|WEAK</evidence_strength>
      <notes>[CLARIFICATION_IF_NEEDED]</notes>
    </action>
    <!-- Additional actions -->
  </verified_actions>
</output_format>

<potential_actions>
{actions_text}
</potential_actions>
"""
    return prompt

def generate_minutes_prompt(topics: List[Dict[str, Any]], action_items: List[Dict[str, Any]]) -> str:
    """
    Generate XML prompt for meeting minutes creation.
    
    Args:
        topics: List of topics with their details
        action_items: List of action items
        
    Returns:
        Formatted XML prompt string
    """
    # Create context with all processed information
    topics_text = ""
    for topic in topics:
        decisions_text = ""
        for decision in topic.decisions:
            decisions_text += f"""<decision>
            <description>{decision.description}</description>
            <decision_makers>{', '.join(decision.decision_makers)}</decision_makers>
            <evidence_strength>{decision.evidence_strength}</evidence_strength>
        </decision>"""
        
        key_points_text = ""
        for point in topic.key_points:
            key_points_text += f"""<point>
            <summary>{point['summary']}</summary>
            <speaker>{point['speaker']}</speaker>
            <evidence_strength>{point['evidence_strength']}</evidence_strength>
        </point>"""
        
        topics_text += f"""<topic>
        <id>{topic.id}</id>
        <name>{topic.name}</name>
        <summary>{topic.summary}</summary>
        <status>{topic.status}</status>
        <key_points>
            {key_points_text}
        </key_points>
        <decisions>
            {decisions_text}
        </decisions>
    </topic>"""
    
    actions_text = ""
    for action in action_items:
        actions_text += f"""<action>
        <description>{action.description}</description>
        <assignee>{action.assignee}</assignee>
        <deadline>{action.deadline}</deadline>
        <evidence_strength>{action.evidence_strength}</evidence_strength>
        <status>{action.status}</status>
    </action>"""
    
    prompt = f"""<instructions>
  Create formal meeting minutes from the analyzed information.
  
  The minutes should:
  1. Begin with a clear executive summary
  2. Organize information by topics discussed
  3. Highlight decisions made and their evidence strength
  4. Include a comprehensive action items list with assignees and deadlines
  5. Be concise yet complete, focusing on key information
  
  Format the minutes in a professional, readable style.
</instructions>

<output_format>
  <meeting_minutes>
    <executive_summary>[CONCISE_SUMMARY_OF_MEETING]</executive_summary>
    
    <topics>
      <topic>
        <name>[TOPIC_NAME]</name>
        <summary>[TOPIC_SUMMARY]</summary>
        <key_points>
          <point>[KEY_POINT_1]</point>
          <point>[KEY_POINT_2]</point>
          <!-- Additional key points -->
        </key_points>
        <decisions>
          <decision>
            <description>[DECISION_DESCRIPTION]</description>
            <decision_makers>[WHO_MADE_DECISION]</decision_makers>
            <evidence_strength>[EVIDENCE_STRENGTH]</evidence_strength>
          </decision>
          <!-- Additional decisions -->
        </decisions>
      </topic>
      <!-- Additional topics -->
    </topics>
    
    <action_items>
      <action>
        <description>[ACTION_DESCRIPTION]</description>
        <assignee>[RESPONSIBLE_PERSON]</assignee>
        <deadline>[DEADLINE]</deadline>
        <evidence_strength>[EVIDENCE_STRENGTH]</evidence_strength>
      </action>
      <!-- Additional actions -->
    </action_items>
  </meeting_minutes>
</output_format>

<meeting_data>
  <topics>
    {topics_text}
  </topics>
  <action_items>
    {actions_text}
  </action_items>
</meeting_data>
"""
    return prompt

def generate_context_for_analysis(topics, actions, decisions) -> str:
    """
    Generate context information for segment analysis.
    
    Args:
        topics: List of existing topics
        actions: List of existing action items
        decisions: List of existing decisions
        
    Returns:
        Context string in XML format
    """
    topics_context = ""
    for topic in topics:
        topics_context += f"""<topic>
        <id>{topic.id}</id>
        <name>{topic.name}</name>
        <summary>{topic.summary}</summary>
    </topic>"""
    
    actions_context = ""
    for action in actions:
        actions_context += f"""<action>
        <description>{action.description}</description>
        <assignee>{action.assignee}</assignee>
        <status>{action.status}</status>
    </action>"""
    
    decisions_context = ""
    for decision in decisions:
        decisions_context += f"""<decision>
        <description>{decision.description}</description>
        <decision_makers>{', '.join(decision.decision_makers)}</decision_makers>
    </decision>"""
    
    return f"""<topics>
    {topics_context}
    </topics>
    <actions>
    {actions_context}
    </actions>
    <decisions>
    {decisions_context}
    </decisions>"""