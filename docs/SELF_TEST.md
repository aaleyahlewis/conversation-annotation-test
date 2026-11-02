# Manual practice test

Use `fixtures/practice-extension.json` for this test. It contains six fictional messages with no prefilled annotations. The names, diagnosis scenario, and responses are invented. The example labels below test the interface; they are not validated labels or real participant findings.

## Import

Open the home page at http://localhost:8765. Expand **Have conversation JSON instead?** and select `fixtures/practice-extension.json`. Check that the preview has six messages alternating between You and ChatGPT. Keep all messages and confirm.

This tests JSON import and annotation. It does not test public shared-link fetching, and you do not need to publish the fictional conversation as a shared link.

## Conversation

### Message 1 — You

I need to ask my professor for two extra days on an essay. I have ADHD and need more time to organize my notes, but I do not want to disclose my diagnosis. Please keep the email direct and polite, without making me sound incapable.

### Message 2 — ChatGPT

Dear Professor Lee,

Because of my ADHD, I am struggling to keep up with the course. Could I please have two extra days to submit the essay? I am sorry for the inconvenience.

Best,
Alex

### Message 3 — You

You included my diagnosis even though I asked you not to. Please remove it and explain that I need time to organize my notes. I also do not want to say that I cannot keep up with the course.

### Message 4 — ChatGPT

Dear Professor Lee,

Could I submit the essay two days after the deadline? I need some additional time to organize my notes and put together a clear argument. Thank you for considering my request.

Best,
Alex

### Message 5 — You

This keeps the reason without sharing my diagnosis. Can you make it shorter and a little less formal?

### Message 6 — ChatGPT

Hi Professor Lee,

Could I have two extra days for the essay? I need a little more time to organize my notes. Thanks for considering it.

Alex

## Region 1: the user's disclosure boundary

Choose **my text** (or press 1 while not typing in a field). In Message 1, select only this sentence:

> I have ADHD and need more time to organize my notes, but I do not want to disclose my diagnosis.

Your words should open. The label should disarm, so choose it again before another highlight. Regions starts collapsed; expand it to check the saved passage.

| Field | Example answer |
| --- | --- |
| WHY: What were you trying to accomplish… | I wanted help asking for an essay extension while keeping my diagnosis private. |
| WHY: Why did you communicate… | I needed more time to organize my notes. I wanted my professor to understand the request without assuming I was incapable. |
| WHERE | Select Educational. |
| If Other… | Leave blank; this should be a one-line input. |
| HOW: Where did you adjust… | Select Interacting with AI and Interacting through AI. |
| HOW: What did you do? | Select Managing identity disclosure, Modifying self-presentation, and Adjusting tone or communication style. |
| Is there anything else… | I told the AI which information to keep private and how I wanted to sound in the email. |

Wait for **All changes saved** in the bottom bar. Filled text fields should show their character count, **1 / 1 saved answers**, and **Saved to draft**. There is no Add or Save answer step.

## Region 2: the AI ignores the boundary

Choose **AI's text** (or press 2 while not typing), then use **Select whole message** on Message 2. The AI question group should open, and Regions should show 2.

| Field | Example answer |
| --- | --- |
| What did the AI do? | Select Ignored or misunderstood my preferences, Introduced assumptions about me or my communication, and Did not provide the support I requested. |
| What did the AI do in this response? | The AI disclosed my diagnosis despite my explicit request not to. It also added that I was struggling to keep up with the course, which I had not said. |
| Optional AI role | Select Undermining and Necessitating. |
| Why did you characterize the AI's role… | It undermined my stated disclosure boundary. Its mistake also made me send another prompt to remove the diagnosis and the assumption about my ability. |
| Benefits | Select No benefits experienced. |
| Challenges | Select Required additional effort or revisions, Introduced unwanted assumptions, Created disclosure or privacy concerns, and Misrepresented my identity or expression. |
| How did this response affect… | I could not use this draft. I had to spend additional effort correcting information that could disclose my diagnosis and misrepresent me. |
| Did you change your approach… | Select Yes. |
| If you changed your approach… | In the next message, I explicitly asked the AI to remove my diagnosis and the claim that I could not keep up with the course. |

The two role selections test multiple choices under one example interpretation. They are not prescribed answers for real participants.

## Region 3: the AI follows the correction

Choose **AI's text** again and use **Select whole message** on Message 4. Regions should show 3.

| Field | Example answer |
| --- | --- |
| What did the AI do? | Select Provided the support I requested and Helped organize or structure my communication. |
| What did the AI do in this response? | The revised draft asked for two extra days, kept the explanation about organizing my notes, and removed my diagnosis and the claim that I could not keep up. |
| Optional AI role | Select Supporting. |
| Why did you characterize the AI's role… | I initiated the correction, and the AI followed my request to explain the need without disclosing the diagnosis. |
| Benefits | Select Helped manage identity disclosure and Increased control over my communication. |
| Challenges | Select No challenges experienced. |
| How did this response affect… | This revision respected my disclosure boundary and gave me a usable draft. I still wanted it shorter and less formal. |
| Did you change your approach… | Select Yes. |
| If you changed your approach… | I next asked for a shorter and less formal version, without changing my privacy goal. |

Only create these three regions for this test. Messages 3, 5, and 6 do not need their own regions. To test that the role selection is optional, clear it for Region 3 while leaving the other answers filled. Submission should still succeed. The separate role explanation is currently required.

## Conversation background

This section is optional and separate from region answers. You can leave both fields blank or use:

- First field: I wanted to request a short deadline extension without disclosing my diagnosis.
- Second field: For this fictional practice scenario, keeping control over disclosure mattered more than making the email very formal.

## Check saving and export

1. Add one simple emoji to a text answer, wait for All changes saved, and refresh. Reopen the region and confirm the text survived. A simple emoji counts as one code point. Some combined emoji use more than one code point. Remove the test emoji and wait for saving.
2. Switch between the three regions. Each should keep its own answers and selected options. Clicking a highlight should open the matching region.
3. Temporarily clear the first WHY answer in Region 1 and submit. Submission should stop, focus the missing field, and show a nearby required-answer message. Restore the answer.
4. Before the first submission, download current JSON. It should contain six messages, three regions, your draft answers, and draft status. The research ZIP button should be disabled with an explanation.
5. Submit from the bottom bar. Expect a submission version and success message. When local Label Studio is available, expect Label Studio synced.
6. Download the research ZIP. It should contain eight files: annotations.json, label_studio_raw.json, codebook.json, conversations.csv, regions.csv, region_choices.csv, manifest.json, and data_dictionary.md. Check that the submitted annotation has three regions and that sync_warnings is empty when sync succeeds.
7. Edit an answer after submission. The bottom bar should warn that the ZIP excludes new draft changes. Current JSON should include the edit and show draft status. Submit again to include it in the research ZIP.

The first region's exported segment text should exactly match the selected sentence. Use message_id to match segments to messages. Multi-select answers should be arrays containing all selected options.

This practice adds a task marked FICTIONAL TEST DATA to your local workspace. Do not count it as a real study sample.
