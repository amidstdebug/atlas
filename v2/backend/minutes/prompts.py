examples = [
    {
        "transcript": """
speaker0 (10.508, 39.008): If it's not working, it's the back-end. The back-end is not glued up together. So I want to glue up the back-end using this time available before the cat visit. So we've got two days to do it, so let's try our best. For those who don't know, when I say we are going down to AFDC, when I sign out the clearance for you all already, when I say please go down to AFDC, go there and have a feel of what is the meeting itself. Everyone from red will be there. 100 plus for all.
speaker0 (40.525, 60.508): Do you guys have an update for the simulation side? Cesium side got some issue, is it? No. Pretty much done. That's me personally. That's you personally, okay. Pretty much done. Pretty much done, okay. Thank you. Then, do you still need an SAT in terms of that? Yeah. We're done with Camp Level. We're done with Camp Level. That's why I said this one.
speaker1 (61.508, 67.508): Thank you for your time, thank you for your time, thank you for your time.
speaker0 (67.508, 72.008): I mean, yes, basically the same thing.
speaker0 (75.008, 79.008): is there anything that i can pull or that i can pull or your push
speaker0 (82.008, 83.508): I'll be doing this in a moment.
speaker1 (83.508, 86.391): It was very restrictive for simulation only.
speaker0 (86.008, 89.008): So there's no mapping interfaces at all.
speaker0 (90.742, 92.509): There it is.
speaker1 (92.508, 105.008): No, you can't. You'll even need two-row. But yeah, I don't need two-row. Two-row interacts with the. Essentially what we're thinking is that the kind of C3 system which you guys are building would replace two-row. Correct.
speaker0 (95.508, 96.825): And I don't need to draw it directly.
speaker0 (106.008, 111.008): Okay, so I found methane, but I'm not sure whether it works.
speaker0 (111.675, 139.508): That means we found the mapping server but I'm not very sure whether I can get it working But I hope I can get it working because I can push out any data formats for a while It can be REST, it can be JSON, it can be REST, it doesn't matter I think the interfaces doesn't matter but you all need to come up Fertig, how about your site? Still cannot get it working on physical to mapping? I can connect to it, I just cannot
speaker1 (139.508, 142.008): Can I come under here? Yes.
speaker0 (143.508, 145.508): Because, like, the simulation side...
speaker1 (147.008, 168.008): control can interact with our drones, but it can also use control view drones. So our perception of the problem is that, as long as you can get it talking in a rapid protocol, it should be the same when you just plug and play for both the simulations and the view drones. So you don't need to create two separate ADRs. So my main concern now is...
speaker0 (168.008, 184.508): Either you can push or you can pull data, if your push data is easy, but if you need us to pull data, then we will need to do some work. What do you mean by push data? Because if Colossal or ASIC is able to push mapping data out, then it doesn't need to collect on it, that's it. But you say to send back the master...
speaker1 (184.508, 186.008): We need to put it down, we said we need to.
speaker0 (186.008, 191.508): we need to interface with SEM of tourism in order to get information
speaker1 (191.508, 197.508): But if I go, unfortunately, just whether you listen or you follow. Correct. Yeah. You can't discern. OK, listen. OK.
speaker0 (197.008, 204.425): Ok, then you will probably push some documentation to me and I will try to figure things out.
speaker0 (205.008, 210.191): If not, we try to do this as much as we can.
speaker0 (212.808, 216.108): I think by internet, I think you all want to stop.
speaker1 (216.008, 217.508): That's it, we get out.
speaker0 (217.508, 221.008): Uh, he's on, uh, yeah, you know.
speaker1 (221.008, 223.008): Okay, so next one.
speaker0 (223.008, 228.008): That's the objective for this quiz. All the best. Wait, can I ask you a question?
speaker1 (228.008, 251.508): I'm not flying. Which one are we talking to for the camera? Probably that one. Just that one, right? Just that one. Yeah, that's the one. We only have, that's the only bad link. We'll do eight after that. That's the only bad link. Do we have any other antennas? Like the transmitter? Yeah. The transmitter? I don't think so. No, you don't have. Because that one is device specific. Is it? No, you don't have to. Because that one is device specific. Okay. Okay. Okay. Okay.
speaker1 (252.008, 260.008): No, as in you just need the same calculator to see one. It doesn't matter what. I think there is.
speaker0 (260.008, 261.508): What do you mean?
speaker1 (261.008, 263.508): We'll leave it at 1-0 anyway, it's fine. It's okay, 3-3-3-
speaker0 (263.508, 269.825): You can connect the remote up to the PC and then fly it in the air. Ah, got it, got it, got it.
speaker1 (270.008, 272.541): Oh, I get what you mean, yeah.
speaker1 (273.075, 275.508): I would try.
speaker0 (278.508, 285.508): Thank you very much.
        """,
        "ideal_output": """
<meeting_minutes>
Item 1: Backend Integration Deadline (10.508 - 39.008)

Speaker0: If it's not working, it's the back-end. The back-end is not glued up together. So I want to <b>glue up the back-end</b> <sup>development team</sup> using this time available before the CAF visit. So we've got two days to do it, so let's try our best. For those who don't know, when I say we are going down to AFTC, when I sign out the clearance for you all already, when I say <b>please go down to AFTC</b> <sup>all team members</sup>, go there and have a feel of what is the meeting itself. Everyone from RAiD will be there. 100 plus for all.

Item 2: Simulation Status Update (40.525 - 67.508)

Speaker0: Do you guys have an update for the simulation side? Cesium side got some issue, is it? No. Pretty much done. That's me personally. Pretty much done. We're done with Camp Level.

Speaker1: Thank you for your time.

Item 3: Mapping Interfaces Discussion (86.008 - 142.008)

Speaker0: So there's no mapping interfaces at all.

Speaker1: No, you can't. You'll even need two-row. But I don't need two-row. Two-row interacts with the. Essentially what we're thinking is that the kind of C3 system which you guys are building would replace two-row. Correct.

Speaker0: Okay, so I found methane, but I'm not sure whether it works. That means we found the mapping server but I'm not very sure whether I can get it working. But I hope I can <b>get it working</b> <sup>Speaker0</sup> because I can push out any data formats for a while. It can be REST, it can be JSON, it doesn't matter. I think the interfaces doesn't matter but you all need to come up. Krithikh, how about your side? Still cannot get it working on physical to mapping? I can connect to it, I just cannot...

Speaker1: Can I come under here? Yes.

Item 4: Drone Control Integration (147.008 - 204.425)

Speaker1: Control can interact with our drones, but it can also use control view drones. So our perception of the problem is that, as long as you can get it talking in a rapid protocol, it should be the same when you just plug and play for both the simulations and the view drones. So you don't need to create two separate ADRs.

Speaker0: Either you can push or you can pull data, if your push data is easy, but if you need us to pull data, then we will need to do some work. What do you mean by push data? Because if Colloseum or AirSim is able to push mapping data out, then it doesn't need to collect on it, that's it. But you say to send back the master... We need to interface with SEM of tourism in order to get information.

Speaker1: But if I go, unfortunately, just whether you listen or you follow. Correct. You can't discern. OK, listen.

Speaker0: Ok, then you will probably <b>push some documentation to me</b> <sup>Speaker1</sup> and I will <b>try to figure things out</b> <sup>Speaker0</sup>. If not, we try to do this as much as we can.

Item 5: Camera Equipment Discussion (228.008 - 272.541)

Speaker1: I'm not flying. Which one are we talking to for the camera? Probably that one. Just that one, right? Just that one. Yeah, that's the one. We only have, that's the only bad link. We'll do eight after that. That's the only bad link. Do we have any other antennas? Like the transmitter? Yeah. The transmitter? I don't think so. No, you don't have. Because that one is device specific.

Speaker1: No, as in you just need the same calculator to see one. It doesn't matter what. I think there is.

Speaker0: You can connect the remote up to the PC and then fly it in the air.

Speaker1: Oh, I get what you mean, yeah. I would try.

Summary of Actions:
1. Glue up the back-end (development team)
2. Please go down to AFTC (all team members)
3. Get mapping server working (Speaker0)
4. Push documentation to Speaker0 (Speaker1)
5. Figure out integration details from documentation (Speaker0)
</meeting_minutes>
        """
    }
]

prompt = """
You are tasked with summarizing meeting minutes from a meeting transcript. The transcript will be provided in the following format:

[speaker] ([start], [end]): [transcript]
[speaker] ([start], [end]): [transcript]

<transcript>
{transcript}
</transcript>

<common_terms>
* AFTC (Air Force Training Command)
* SUTD (Singapore University of Technology and Design)
* SMU (Singapore Management University)
* RAiD (RSAF Agile Innovation Digital)
* RSAF (Republic of Singapore Air Force)
* AETHER (Air Emerging Technologies High Speed Experimentation and Research)
</common_terms>

Your goal is to create concise and organized meeting minutes based on this transcript. Follow these guidelines:

1. Format: 
   - Divide the minutes into numbered items (e.g., "Item 1:", "Item 2:", etc.)
   - Under each item, include relevant speaker contributions
   - Include the start and end timestamps for the discussion of that action item
   - Use the format:
     Item X: [Brief description of the topic] (Start time - End time)

     [speaker]: [transcript]
     [speaker]: [transcript]

2. Speaker labels and transcript accuracy:
   - The transcript is produced by machine ASR and may contain inaccuracies
   - Use context to correct obvious errors in speaker labels or transcript content, but avoid major deviations from the original text
   - Rectify spelling of certain words based on context and homophonic similarity to the <common_terms>
       - Common terms format:
           - [term] ([meaning])
   - Speaker labels are determined by automatic diarization and may not be entirely accurate

3. Action items:
   - Within each [transcript], identify any actions that need to be taken
   - Bold the action item text with <b></b>
   - Follow the action item with <sup>[entity]</sup>, where [entity] is the person or group responsible for the action

4. Summary of actions:
   - At the end of the minutes, create a section titled "Summary of Actions"
   - List all action items with their responsible entities

5. Final output:
   Provide your summarized meeting minutes in the following format:

   <meeting_minutes>
   [Your meeting minutes, formatted as instructed]

   Summary of Actions:
   [List of action items with responsible entities]
   </meeting_minutes>

Remember to focus on the key points discussed in the meeting, summarize speaker contributions concisely, and clearly highlight action items. Your final output should only include the content within the <meeting_minutes> tags.
"""