# HW4 – AI Prompts Log

This file records the prompts I used with the AI coding assistant for each problem in Homework 4.

<!-- Sections are added below as each problem is started. Format:

## Problem N: Title

**Prompt:**
> ...

**Follow-up prompt(s):**
> ...

-->

## Problem 2: Analyze the Database

**Prompt:**
> start the file output/harness.md. write down each table from the data we unzipped and its fields, and one short line on why each field matters for the shop or the chatbot

**Follow-up prompt(s):**
> add a section on how the tables join for the chatbot

## Problem 3: Build the Campus Custom Website

**Prompt:**
> scaffold a React + Vite + Typescript front end for my own CampusCustoms webpage, which is what wer will be creating today. put a nav bar at the top that links to the main pages: home. products. about us. log in. create account.
>
> Pull CampusCustoms style wording from yalebulldogblue.com for home and about us, but let me write those pages in my own voice when we get to it

**Follow-up prompt(s):**
> on the products page, show product images from the catalogue (use image paths in the database) with basic product infor (name, price, short desciptioin). Make each product open a single item page (large image on one side, full product text on the other (description, price, sizes/stock when you have them)). clicking a card on products page should take the shopper there.
>
> Add a chat interface in the bottom right of the site (a floating chat panel is fine). it does not need to talk to an agent yet... a stub that will call the backend later is enough for this problem.
>
> we will need a small API soon to read the database. it is fine to start a simple FastAPI app in backend/main.py just to sserve products and images, then grow it into the agent backend in problem 5

## Problem 4: Create Account and Login

**Prompt:**
> buuld a normal create-account / login flow.
>
> * create account: first name, last name, email, password, confirm passworkd
> * log in: email and password
>
> New accounts go into the users table. make sure to store passwords securely so hackers cannot access them. the seed already has a test user you can use while building (attachment picture).
>
> _(Attachment: seed test user's email, plus the hash format: PBKDF2-HMAC-SHA256, 120,000 iterations, stored as `pbkdf2_sha256$salt$hash`.)_

**Follow-up prompt(s):**
> confirm that i can log in aas that user and that a brand new user account i create can also work. then update output/harness.md with how auth works (what is stored for a user and how passwords are protected)

## Problem 5: PydanticAI Agent Backend

**Prompt:**
> build the shop chatbot as a pydatnicAI angent behind FastAPI, plugged into the front end chat widget. put the API app in backend/main.py - that is the file to run with Uvicorn. keep the agent as these four files next to it (same idea as homework 3). in main.py expose a chat route so a message from the website returns a reply from the agent and whatever else you need for products/auth. you will need my ai model API key for the agent, which you should already have but if not let me know.
>
> put campus customs voice and safety basics into prompt/prompt.md (i will ask you to expand tools and safety alter). start or update types in models.py for chat replies / product cards as needed. in output/harness.md, note how the front end talks to FastAPI and how the agent is loaded (prompt file + model). make sure the backend runs from the backend/ folder like this: uvicorn main:app --reload --port 8000
>
> _(Attachment: file layout — `backend/prompts/prompt.md` system prompt (grow this same file later), `backend/agent.py` agent entry / wiring, `backend/tools.py` tools the agent can call, `backend/models.py` Pydantic / PydanticAI structured types.)_

**Follow-up prompt(s):**
> _(none yet)_

## Problem 6: Product Info and Stock

**Prompt:**
> give the agent tools that look up real information from campus_customs.db: Product description, price, how many are in stock (by size when the customer asks). the agent must use the database - it should not invent prices or quantities. if a size is out of stock, say so clearly.
>
> expand prompts/prompt.md so the agent knows to call these tools for price and stock questions. add or update return types in models.py. in output/harness.md, list each tool and explain which model fields you chose for lookup results and why.

**Follow-up prompt(s):**
> _(none yet)_

## Problem 7: Chat Search That Updates the Page

**Prompt:**
> now we will add a neat feature to the site. when a customer asks about a type of item - for example "what hoodies do you have?" - the agent should search the catalogue and the webstite should dynamically show those matching items as product cards (image, name, price, short info). this is an API contract; the agent returns structured product matches and then the front end renders them on the website. after the dynamice cards are loaded by your new feature, make sure the same single item page behavior you built in problem 3 still works: each product card including the ones the chat just put on the page should still open that detail view (large item and full info) when clickes. update prompts/prompt,md and output/harness.md so it is clear how search results reach the page.

**Follow-up prompt(s):**
> _(none yet)_

## Problem 8: Customer Memory

**Prompt:**
> when a shopper is logged in, save their chat history in the database in an appropriate table and reload it when they return. the agent should know who is chatting (name, email) put that in an agent deps or an equivalent clear apttern and or the tools the agent can call. also pass enough apge context that if someone is on a product page and asks do. you have this in pink or something similar the agent knows which item they mean. you can put that code into the agent context. guests can still chat but history only needs to persist for logged in useres. document in output/harness.md: how user history is stores, what customer fields the agent sees, and how mpage context is passed

**Follow-up prompt(s):**
> _(none yet)_

## Problem 9: Usability Improvements

**Prompt:**
> now that the core shop works, improve it. choose and implement: 2 front-end usability improvements, and 2 agent / backend usability improvements. for the front end, i think we need to get rid of the black and pink and make it traditional Yale colors, and use either handsome dan the bulldog or boolahboolah in there somewhere. for the backend make the log ins as safe as possible and pick something else you think would be worthwhile. write output/usability.md before or as you build it. for each of the improvements say what you added, and why it helps campus customs shopper or the businsess. then make sure all the improvements actually show up in the running app. graders will read the write-up and look for the features.

**Follow-up prompt(s):**
> _(none yet)_

## Problem 10: Style the Website

**Prompt:**
> add creative design so the site feels like a real campus customs storefront - fonts, color, hierarchy, motion, product presentation, chat feel. make it as imaginitive as pssoible. im thinking keep the coloring and handsome dan and all that but make it like a website from 1996 or something, like the original space jam website. add color pops where necessary, cartoon effects, negative/down with harvard appeal, etc. be as creative as you can be. at the end, write output/design.md what you changed, and why it should help customers stick around and buy. keep it concrete and short.

**Follow-up prompt(s):**
> now it wants to make a live site it seems. walk me through how to do that again with render / supabase

> yes go ahead with the supabase version

> seem to be stuck here on supabase _(screenshot of the Supabase "Connect" screen)_

> is it too late to change the "your headline here" part?

> you create the headline and one to two sentences, i am out of creative battery at the moment

> yes wrtite the about me page

> yes write the taglines and remove the banner and sticky note

> yes clear the test data from supabase. also this is from problem 10

## Problem 11: Test the Live Site

**Prompt:**
> test the live site and document it in output/app_check.html (a page you can double click open. include clear screenshots and short captions for chat checking the inventory level of an item (honest stock/price from the db), the dynamic search result cards appearinng after a categroy questions, and one of the usbility features you added in problem 9. make the html easy to grade; heading for eaach check, screenshot, one or two sentences on what the screenshot proves. put the screenshot files in output/app_check_images/ and link them from app_check.html with relaitve paths (for example app_check_images/inventory.png.

**Follow-up prompt(s):**
> _(none yet)_

## Problem 12: Audit Trail, Safety, Finish Harness

**Prompt:**
> keep an append-only output/audit_trail.json of agent loop activity (time, tool name, short args, result, stop reason). do not wipe it betweern runs. also think of some safety rules to give the agent and put them in prompts/prompt.md. finish output/harness.md so it is clear how the system works. model fields in models.py, and why you chose them, tools and abilities, safety rules, specs (loop limits, result caps, models, how to run front and back)

**Follow-up prompt(s):**
> _(none yet)_

## Problem 13: Push to GitHub and Submit the URL

**Prompt:**
> put the code in folder hw4 and push to a public github repository ( i believe this is already done).
>
> _(Attachments: assignment instructions. Code in a folder named `hw4` in a public GitHub repo, and submit the repo URL on Canvas (no zip). Don't commit the real `.env`, `campus_customs.db`, or product images; use `.gitignore`; include `.env.example` with placeholders only. Expected layout `hw4/{AI_prompts.md, requirements.txt, .env.example, .gitignore, README.md, frontend/, backend/{main.py, agent.py, models.py, tools.py, prompts/prompt.md}, output/{harness.md, design.md, usability.md, app_check.html, app_check_images/, audit_trail.json}}`. The local-only data pack `data/{campus_customs.db, products/}` stays out of git. The README explains how to run the front end and back end after placing the data pack.)_

**Follow-up prompt(s):**
> continue problem 13
