# Workspace build guide (the ClickUp half)

Click-by-click steps to build the ClickUp side of Inbox-to-Action on a **Free Forever** workspace, written so a person or a browser-driving agent can follow it quickly. UI names are taken from ClickUp's help centre (articles updated October 2026). ClickUp changes its interface often: if a label differs, search the help centre for the article named in brackets.

Time: about 2 to 2.5 hours, plus the live test.

## 0. Before you start: the Free plan budget

These limits are lifetime or monthly and some can't be undone, so read them first.

| Limit (Free Forever) | What it means for this build |
|---|---|
| **60 Custom Field uses, lifetime** ("Custom Fields uses") | Every value set on a task counts: by you, by the form, by an automation or by the API. Creating fields and options is free. Budget it (see 0.1). |
| **1 Form** ("Form view feature availability and limits") | Only one form in the whole workspace. Build it once, carefully. |
| **No sharing, embedding or exporting of forms on Free** (same article) | There's no public link on Free. Submit the form from inside ClickUp for the demo. A public link needs Unlimited or above. |
| **5 active Automations, 100 actions per month** ("Automations feature availability and limits") | This build uses 3. Each action that runs counts. |
| **60 Dashboard uses, lifetime, and viewing counts** ("Dashboards feature availability and limits") | Build the dashboard in one sitting, screenshot it, don't keep reopening it. Dashboards can't be shared outside the workspace on any plan. |
| **5 Spaces** | Only 1 needed. |

### 0.1 Custom Field budget

Per end-to-end test: form-filled custom fields (keep it to 1: Budget band) + 2 AI writes (AI Summary, AI Priority) = **3 uses**. That leaves room for about 15 full runs after setup, so:

- Don't fill custom fields by hand while building or testing.
- For rehearsals, leave `CLICKUP_AI_SUMMARY_FIELD_ID` and `CLICKUP_AI_PRIORITY_FIELD_ID` blank in `.env`: the service then only posts the comment, which costs nothing.
- Do the final recorded run with the IDs filled in.

## 1. Account and API token

1. Sign up at clickup.com (Free Forever). Workspace name suggestion: `Synthlance Delivery`.
2. Activate Automations if asked: the Workspace owner must turn on the **Automation ClickApp**.
3. Personal API token ("Authentication", developer docs): click your **avatar** (upper-right) > **Settings** > sidebar **Apps** (direct link: app.clickup.com/settings/apps) > under **API Token** click **Generate** > **Copy**. Tokens start `pk_` and never expire.
4. Paste it into the project's `.env` as `CLICKUP_API_TOKEN` yourself. Never into chat, a note, a screenshot or the repo.

## 2. Space "Client Delivery" ("Create and edit Spaces")

1. Global Navigation > **Home**. In the Home Sidebar, click the **plus icon** (upper-right) > **Space**.
2. Name: `Client Delivery`. Optional description: "Client intake to delivery". Pick an icon and colour.
3. Click **Continue**.
4. Statuses: customise the workflow so it reads: `triage` (Not started/active), `approved` (active), `in progress` (active), `review` (active), `complete` (Done/closed). Delete any default you don't need.
5. Required views: keep **List** (required). Add **Board** if offered.
6. Click **Create Space**.

## 3. Lists ("Create a List")

In the Spaces section of the Home Sidebar, hover over **Client Delivery** > **plus icon** > **List**. Create three, in order:

1. `Intake`
2. `Active Projects`
3. `Done`

Open the Intake list and note the number in the browser URL: that is `CLICKUP_INTAKE_LIST_ID`.

## 4. Custom Fields on Intake ("Create Custom Fields")

Open **Intake** in List view. In the upper-right corner above the task table click the **plus icon** (or **Add**), search for the field type, name it, add options, click **Create**. Creating fields and options does not use the 60.

| Field name (exact) | Type | Options |
|---|---|---|
| `Service type` | Dropdown | Workspace setup, Automation, Integration / API, AI assistant, Consulting / other |
| `Budget band` | Dropdown | Under $500, $500 - $2,000, $2,000 - $5,000, Over $5,000, Not sure yet |
| `Urgency` | Dropdown | Urgent, High, Normal, Low |
| `AI Summary` | Text (the paragraph one, not Short Text) | none |
| `AI Priority` | Dropdown | Urgent, High, Normal, Low (exact spelling, the service matches by name) |

`Service type` options must match `SERVICE_TYPES` in `.env` (the defaults above already do). `setup_fields.py` checks all of this and prints the field IDs.

Tip: add these fields at the Space level instead (Custom Field Manager > select the Space > **Create new**) if you want them to stay visible when tasks move to Active Projects.

## 5. Intake Form ("Create and access Forms", "Intro to Forms and Form view")

1. Open the **Intake** list. In the **Views Bar** select **Form**.
2. In the **Create a Form** modal choose **Start from scratch** (or the Project Intake template, then trim it).
3. Confirm the List for submissions is **Intake**.
4. Form title: `Start a project`. Description: "Tell us what you need. We reply within one working day."
5. Questions (keep custom-field questions to one, see 0.1):
   - **Task name** labelled "Your name and business"
   - **Task description** labelled "What do you need? Include your deadline and any tools you already use." (free text; the AI reads this)
   - **Budget band** (the Dropdown field)
   - Name, email and deadline go inside the description prompt rather than separate custom fields, to save uses.
6. Leave it **Published** (the default).
7. On Free you can't copy a public link. To test, open the Form view and submit it yourself from inside ClickUp. On the Unlimited plan or above: **Copy link** (upper-right), and the caret next to it opens **Sharing settings**.

## 6. Kickoff checklist template ("Use task templates", "Use task checklists")

1. In **Active Projects**, create a task named `Kickoff template`.
2. Add subtasks: `Discovery call`, `Scope document`, `Build`, `Review`, `Handover`.
3. In the task, scroll to **Checklists** > **Create checklist** named `Kickoff`, items: Confirm budget and deadline; Get workspace access; Agree success criteria; Book weekly check-in.
4. Task's upper-right **ellipsis ...** > **Templates** > **Save as Template**. Name `Kickoff checklist`. Import options: **Customize import items**, tick Subtasks, Checklists, Description. **Save Template**.
5. Delete or archive the source task afterwards.

Don't set it as the List's default task template: ClickUp says automations using the Task created trigger with Apply a template won't fire in Lists with a default task template.

## 7. Native automations, 3 of the free 5 ("Create an Automation", "Use Automation Triggers", "Use Automation Actions")

Open the **Intake** list, upper-right **robot icon** > **Create Automation** > build a custom one.

**Automation 1: new enquiry**
- Trigger: **Task or subtask created**. **Tasks or subtasks** dropdown: **Tasks**. **Created by**: tick **Forms**.
- Actions: **Change status** to `triage`; **Change assignees** to yourself; **Change due date** > **Days after trigger date** = 2.
- Name: `New enquiry: triage, assign, due in 2 days`. **Create**.

**Automation 2: approved**
- Location: Intake list. Trigger: **Status changes**, To: `approved`.
- Actions: **Apply a template** > `Kickoff checklist`; then **Move to List** > `Active Projects`.
- Name: `Approved: kickoff template and move to Active Projects`. **Create**.

**Automation 3 (optional): finished**
- Location: Active Projects. Trigger: **Status changes**, To: `complete`. Action: **Move to List** > `Done`.

Note: these use automation actions (100/month) but not Custom Field uses. The AI layer is not an automation; it runs on the API webhook (step 9), because the **Call webhook** / task webhook actions are Business plan only.

## 8. Dashboard ("Create a Dashboard", "Dashboards feature availability and limits")

Each create, view, add, edit or remove counts against 60 lifetime uses. Plan the cards first and build in one go.

1. Hover over **Client Delivery** in the sidebar > **plus icon** > **Dashboard** > **Start from scratch**.
2. Name: `Client Delivery overview`.
3. **+ Card** for each (Location: the Client Delivery Space):
   - Status overview / tasks by status (pie or bar)
   - Tasks by `Service type` (Custom Field chart)
   - Workload by assignee
   - Count of tasks in `approved` and later (a calculation or status card)
4. Screenshot it once it has data from the test runs. Don't keep it open on auto refresh.

## 9. Connect the AI layer

On the machine running the service, in the project folder:

1. `cp .env.example .env`, then add `CLICKUP_API_TOKEN` (step 1) and the Anthropic key yourself.
2. `python setup_fields.py --workspaces` > copy `CLICKUP_TEAM_ID` into `.env`.
3. Add `CLICKUP_INTAKE_LIST_ID` (step 3).
4. `python setup_fields.py` > must end with "All fields look right." Copy the printed field IDs into `.env` (or leave them blank for zero-cost rehearsals, see 0.1).
5. `python -m inbox_to_action.server`, check `http://localhost:8000/health` returns `{"ok": true}`.
6. Expose it over HTTPS (Cloudflare Tunnel: `cloudflared tunnel --url http://localhost:8000`, or ngrok). Note the `https://` URL.
7. `python register_webhook.py --endpoint https://<that-url>/clickup/webhook`. The signing secret is saved to `.env`. Restart the server so it loads the secret.
8. `python register_webhook.py --list` shows the webhook with `health=active`.

A quick tunnel URL changes on restart; if it does, register a new webhook (and delete the old one from the API or ignore it; it will go to failing and then suspended on its own).

## 10. End-to-end test

1. Rehearse first with the AI field IDs blank (comment only, no uses spent).
2. Open the Intake **Form** view and submit a realistic, clearly fictional enquiry, e.g. "Sam Carter, Brightside Dental (demo)" asking for enquiry tracking with a deadline next month, budget band $500 - $2,000.
3. Within a few seconds: the task appears in Intake with status `triage`, assignee and due date (automation 1); the server log shows `processed`; the task gets the AI comment.
4. Fill the field IDs in `.env`, restart, submit one more enquiry: AI Summary and AI Priority fill in too.
5. Change the status to `approved`: the kickoff subtasks and checklist appear and the task moves to Active Projects (automation 2). The service ignores those subtasks by design.
6. Check `python register_webhook.py --list` still shows `active` with `fails=0`.
7. Open the dashboard once and screenshot it.

If nothing arrives: check the server log for `Rejected request` (secret wrong or server not restarted), the webhook health (`--list`), and that the tunnel is still up.

## 11. What to capture

Screen recording, 60 to 90 seconds, silent with captions, plus a clean SRT caption file:
1. Fill in and submit the form.
2. The task appears in Intake with status, assignee and due date.
3. A few seconds later: AI Summary, AI Priority and the AI comment appear (refresh if needed).
4. Change status to approved: it moves to Active Projects with the kickoff checklist.
5. The dashboard with the counts.

Stills:
- The form (as it looks to someone filling it in)
- The Intake list with the custom field columns showing AI Summary and AI Priority
- One task open with the AI comment
- The Automations list showing the 3 automations
- The dashboard
- The architecture diagram from the README (render the Mermaid block on GitHub)
- Terminal: `pytest` passing and `dry_run.py` output

Before saving any screenshot: no `pk_` token, no `sk-ant-` key, no webhook secret, no `.env` contents, no real names or emails on screen. Use the fictional demo enquiry only.


## 12. Lessons from the live build (27 October 2026)

- **"Apply template" clears the task's assignee** (and due date). Add a third action to the approval automation, `Update assignees`, after the template and the move.
- **Declining ClickUp's AI "suggested list settings"** when you create a list (click *No thanks*) avoids it creating extra custom fields.
- **Checklist items** are added from the checklist's `...` menu > *Add Item*. The `+` under a checklist opens an assignee picker, not a text box.
- **Status pickers in automations** group statuses (Not started / Active / Closed). Tick individual statuses by expanding the group with its arrow; the group checkbox selects all of them.
- **Forms on Free** can only be filled in from the Form view (Preview tab) inside ClickUp; there is no public link.
- **Order of setup for the AI layer:** open the tunnel first, register the webhook (it returns the signing secret), then start the service. The service refuses to start without the secret.
- **Cost:** one enquiry uses one Claude call (a few thousand tokens) and, with both AI fields set, two Custom Field uses.
