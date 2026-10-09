"""Generate the fake demo dataset (PRD Section 13) into tests/demo_data/.

All content is invented sample data: no real IDs, accounts or personal records.
Creates PDF, DOCX, PPTX and TXT files across School, Finance, Personal, Work and
Government topics, files with unhelpful names, Taglish documents, and a Bad/ folder
with files that must be skipped or ignored. Modified times are set relative to today
so date clues (kahapon, last month, Marso) can be tested.

Usage: python tests/make_demo_data.py [target_dir]
"""

from __future__ import annotations

import os
import shutil
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent / "demo_data"

# (relative path, date spec, title, paragraphs). Date spec: int days ago, "yesterday",
# "last_month", "two_months_ago", or ("month", m) for the most recent past month m.
DOCS: list[tuple[str, object, str, list[str]]] = [
    ("School/Biology/mangrove_research_draft.docx", 40, "Mangrove Ecosystems of Bataan: Research Draft", [
        "Group 4 research paper para sa Biology 2. Members: Ana Reyes, Ben Cruz, Carla Santos.",
        "Introduction. Mangrove forests along the coast of Bataan protect coastal barangays from storm surge and serve as nursery grounds for fish, crabs and shrimp. Ayon sa mga mangingisda sa Orion, mas marami ang huli nila malapit sa mga bakawan.",
        "Methodology. We will compare two sites: a restored mangrove area in Balanga and a cleared fishpond area in Pilar. At each site we count seedlings in five 10 by 10 meter plots and measure water salinity at low tide.",
        "Expected results. We expect higher seedling density and more juvenile fish in the restored site. Ang deadline ng first draft ay sa Biyernes, kailangan pa ng tatlong sources tungkol sa mangrove restoration.",
    ]),
    ("School/Biology/photosynthesis_lesson.pptx", ("month", 3), "Photosynthesis", [
        "Photosynthesis||How plants turn light into chemical energy. Biology 2, Unit 3.||Intro slide, ask the class what plants eat.",
        "The equation||6 CO2 + 6 H2O + light energy -> C6H12O6 + 6 O2|Happens in the chloroplast||Emphasize that oxygen is a by-product.",
        "Light-dependent reactions||Take place in the thylakoid membrane|Chlorophyll absorbs light, water is split, ATP and NADPH are produced||",
        "Calvin cycle||Takes place in the stroma|Carbon fixation by the enzyme RuBisCO|Uses ATP and NADPH to build glucose||Quiz next meeting on the Calvin cycle.",
    ]),
    ("School/Biology/cell_division_reviewer.pdf", 75, "Reviewer: Cell Division (Mitosis and Meiosis)", [
        "Mitosis produces two identical diploid daughter cells and is used for growth and repair. Phases: prophase, metaphase, anaphase, telophase, followed by cytokinesis.",
        "During prophase the chromatin condenses into chromosomes and the nuclear envelope breaks down. In metaphase the chromosomes line up at the metaphase plate.",
        "<pagebreak>",
        "Meiosis produces four genetically different haploid cells, the gametes. It has two divisions, meiosis I and meiosis II. Crossing over happens in prophase I and increases genetic variation.",
        "Tip sa exam: tandaan na ang mitosis ay para sa body cells at ang meiosis ay para sa sex cells.",
    ]),
    ("School/History/rizal_noli_essay.docx", 120, "Themes of Social Injustice in Noli Me Tangere", [
        "Jose Rizal wrote Noli Me Tangere in 1887 to expose the abuses of the Spanish friars and colonial officials in the Philippines.",
        "The character of Crisostomo Ibarra represents the educated Filipino who believes in reform through education. His plan to build a school is blocked by Padre Damaso and Padre Salvi.",
        "Sisa's tragedy shows how the poor suffered the most under the colonial system. Her madness after losing her sons Basilio and Crispin is one of the most painful parts of the novel.",
        "In conclusion, the novel remains relevant today because it reminds readers to question power and to care for the powerless.",
    ]),
    ("School/History/philippine_revolution_timeline.pdf", 140, "Timeline of the Philippine Revolution", [
        "1892: Andres Bonifacio founds the Katipunan in Tondo, Manila, after the arrest of Jose Rizal.",
        "August 1896: The Cry of Pugad Lawin. Katipuneros tear their cedulas as a sign of revolt against Spain. The revolution begins.",
        "March 1897: The Tejeros Convention elects Emilio Aguinaldo as president, causing a split with Bonifacio.",
        "December 1897: The Pact of Biak-na-Bato. Aguinaldo agrees to go into exile in Hong Kong.",
        "June 12, 1898: Philippine independence is declared in Kawit, Cavite.",
    ]),
    ("School/Math/calculus_problem_set_3.pdf", 60, "Calculus 1 Problem Set 3: Derivatives", [
        "Instructions: Show your complete solution. Due next Tuesday.",
        "1. Find the derivative of f(x) = 3x^4 - 5x^2 + 7 using the power rule.",
        "2. Use the product rule to differentiate g(x) = x^2 sin x.",
        "3. Use the quotient rule to differentiate h(x) = (2x + 1)/(x - 3).",
        "4. Apply the chain rule: find dy/dx if y = (4x^3 + 2)^5.",
        "5. A ball is thrown upward with height s(t) = -4.9t^2 + 20t. Find its velocity at t = 2 seconds.",
    ]),
    ("School/Math/statistics_notes.txt", 50, "Stats notes", [
        "STATISTICS NOTES - Measures of central tendency at variability",
        "Mean = sum ng lahat ng values divided by number of values. Median = yung gitnang value kapag naka-sort. Mode = yung pinakamadalas lumabas.",
        "Standard deviation: kunin muna ang mean, ibawas ang mean sa bawat value, i-square, i-average (divide by n - 1 kung sample), tapos kunin ang square root. Ito ang sukat kung gaano kalat ang data.",
        "Example: 2, 4, 4, 4, 5, 5, 7, 9. Mean is 5, population standard deviation is 2.",
    ]),
    ("School/Thesis/thesis_defense_reminders.txt", "yesterday", "Thesis defense reminders", [
        "Reminder sa lahat ng graduating students ng BSIT 4A: ang thesis defense schedule ay naka-post na sa bulletin board ng CCS building.",
        "Each group has 20 minutes for the presentation and 10 minutes for Q&A ng panel. Magdala ng tatlong printed copies ng manuscript, naka-ring bind.",
        "Bawal ang late. Dapat nandoon kayo 30 minutes before your slot. Formal attire po. Good luck sa lahat!",
    ]),
    ("School/Thesis/chapter2_rrl.docx", 90, "Chapter 2: Review of Related Literature", [
        "This chapter presents studies on the adoption of e-wallets such as GCash and Maya among college students in the Philippines.",
        "Local studies. A 2023 survey of university students in Metro Manila found that convenience and promos were the main reasons for using e-wallets, while fear of scams was the main barrier.",
        "Foreign studies. Research based on the Technology Acceptance Model shows that perceived usefulness and perceived ease of use predict the intention to use mobile payment apps.",
        "Synthesis. The reviewed literature suggests that trust and security features strongly affect continued use of e-wallets among young users.",
    ]),
    ("School/Thesis/defense_presentation.pptx", 20, "E-Wallet Adoption Among College Students", [
        "E-Wallet Adoption Among College Students||Thesis defense, BSIT 4A, Group 2||Greet the panel first.",
        "Statement of the problem||What factors affect e-wallet use among students?|Does trust affect continued use?||",
        "Results||312 respondents|78% use GCash weekly|Trust had the strongest effect on continued use||Show the regression table if asked.",
        "Recommendations||Banks and e-wallet providers should promote scam awareness|Future studies may include senior high school students||",
    ]),
    ("School/English/book_report_old_man_and_the_sea.docx", 160, "Book Report: The Old Man and the Sea", [
        "The Old Man and the Sea by Ernest Hemingway tells the story of Santiago, an old Cuban fisherman who has gone 84 days without catching a fish.",
        "On the 85th day he hooks a giant marlin far out in the Gulf Stream and struggles with it for three days. On the way home, sharks eat the marlin until only the skeleton remains.",
        "The novel is about perseverance and dignity in defeat. Santiago loses the fish but not his spirit.",
    ]),
    ("School/Org/student_council_minutes.docx", 35, "Student Council Meeting Minutes", [
        "Meeting called to order at 4:00 PM sa SC office. Present: President, VP, Secretary, Treasurer, at 5 class representatives.",
        "Agenda 1: Intramurals budget. Napagkasunduan na PHP 25,000 ang budget para sa jerseys, trophies at tubig. Treasurer will canvass three suppliers.",
        "Agenda 2: Clean-up drive sa Sabado. Bawat section ay magdadala ng sariling walis at sako.",
        "Meeting adjourned at 5:15 PM.",
    ]),
    ("School/Physics/projectile_motion_lab_report.pdf", 100, "Lab Report: Projectile Motion", [
        "Objective: To determine the relationship between launch angle and horizontal range of a projectile.",
        "Procedure: A spring launcher fired a steel ball at angles of 15, 30, 45, 60 and 75 degrees. Each angle was tested five times and the landing points were measured with a meter stick.",
        "Results: The maximum range of 2.41 meters was observed at 45 degrees. Complementary angles such as 30 and 60 degrees gave nearly equal ranges.",
        "Conclusion: The results agree with the theory that range is maximum at 45 degrees when air resistance is negligible.",
    ]),
    ("School/Chemistry/titration_lab_notes.txt", 110, "Titration lab notes", [
        "Acid-base titration lab. Titrant: 0.1 M NaOH. Analyte: 25 mL vinegar sample. Indicator: phenolphthalein.",
        "Endpoint is reached when the solution turns faint pink and stays pink for 30 seconds. Average volume of NaOH used: 18.4 mL.",
        "Computed acetic acid concentration ng vinegar: about 4.4 percent. Medyo malapit sa label na 4.5 percent.",
    ]),
    ("School/Filipino/sanaysay_wika.docx", 130, "Sanaysay: Ang Wika Bilang Kaluluwa ng Bayan", [
        "Ang wika ay hindi lamang kasangkapan sa pakikipag-usap. Ito ang nagdadala ng ating kasaysayan, kultura at pagkakakilanlan bilang mga Pilipino.",
        "Sa panahon ng social media, madalas nating ihalo ang Ingles at Filipino. Hindi ito masama, ngunit dapat nating pagyamanin pa rin ang sariling wika.",
        "Bilang mag-aaral, tungkulin nating gamitin nang wasto ang Filipino sa pagsulat at pagsasalita upang manatili itong buhay para sa susunod na henerasyon.",
    ]),
    ("Finance/Bills/meralco_bill_september.pdf", "last_month", "Meralco Electric Bill - September 2026", [
        "Customer: Sample Household, Account No. 0000-0000-01 (sample). Billing period: August 15 to September 14, 2026.",
        "Total kWh used: 312 kWh. Generation charge, transmission charge, system loss charge and distribution charge are itemized below.",
        "Total amount due: PHP 3,482.50. Due date: September 28, 2026. Mas mataas ng 18% kumpara sa nakaraang buwan dahil sa aircon.",
        "Pay through GCash, Bayad Center, or any Meralco business center. Late payment may result in disconnection.",
    ]),
    ("Finance/Bills/meralco_bill_august.pdf", "two_months_ago", "Meralco Electric Bill - August 2026", [
        "Customer: Sample Household, Account No. 0000-0000-01 (sample). Billing period: July 15 to August 14, 2026.",
        "Total kWh used: 264 kWh. Generation charge, transmission charge, system loss charge and distribution charge are itemized below.",
        "Total amount due: PHP 2,951.20. Due date: August 28, 2026.",
        "Pay through GCash, Bayad Center, or any Meralco business center.",
    ]),
    ("Finance/Bills/maynilad_water_bill.pdf", 45, "Maynilad Water Bill", [
        "Water service statement for a sample account. Previous reading: 1,204 cubic meters. Present reading: 1,226 cubic meters. Consumption: 22 cubic meters.",
        "Basic charge, environmental charge, sewer charge and FCDA are itemized. Total amount due: PHP 845.75.",
        "Paalala: may scheduled water interruption sa inyong area tuwing Martes ng gabi para sa pipe maintenance.",
    ]),
    ("Finance/Bills/pldt_internet_bill.txt", 30, "Internet bill", [
        "PLDT Home Fiber statement (sample). Plan: Fiber Plan 1699, up to 300 Mbps.",
        "Monthly service fee: PHP 1,699.00. Previous balance: PHP 0.00. Total amount due: PHP 1,699.00.",
        "Due date is on the 20th of the month. Pay via the PLDT app, online banking or partner payment centers.",
    ]),
    ("Finance/Receipts/lazada_order_receipt.pdf", 25, "Order Receipt", [
        "Online order confirmation. Order number: SAMPLE-20260914-001. Seller: Sample Gadget Store Official.",
        "Item: Wireless Bluetooth earbuds with charging case, black. Quantity: 1. Price: PHP 1,299.00. Shipping fee: PHP 45.00. Voucher discount: PHP 100.00.",
        "Total paid: PHP 1,244.00 via GCash. Estimated delivery: 3 to 5 days.",
    ]),
    ("Finance/Receipts/grocery_receipt_sm.txt", 12, "Grocery receipt", [
        "SM Supermarket (sample receipt)",
        "Rice 5kg 285.00\nEggs 1 tray 230.00\nCooking oil 1L 120.00\nCanned sardines x6 132.00\nInstant noodles x10 95.00\nDetergent powder 1kg 110.00",
        "TOTAL 972.00  CASH 1000.00  CHANGE 28.00",
    ]),
    ("Finance/Budget/budget_disyembre.docx", 70, "Budget Plan para sa Disyembre", [
        "Ang monthly budget ko for December: rent PHP 8,000, food PHP 6,000, transportation PHP 2,000, at load PHP 500.",
        "Naglaan din ako ng PHP 3,000 para sa Noche Buena at mga regalo sa inaanak. Target kong mag-ipon ng at least PHP 2,500 ngayong buwan kahit maraming gastos sa Pasko.",
        "Tip: hatiin ang 13th month pay, kalahati sa savings at kalahati sa gastos.",
    ]),
    ("Finance/Budget/household_expenses_2026.docx", 15, "Household Expenses 2026", [
        "<table>Month|Rent|Electricity|Water|Internet|Groceries\nJanuary|8000|2650|780|1699|9500\nFebruary|8000|2510|760|1699|9100\nMarch|8000|2890|800|1699|9800",
        "Notes: electricity goes up during summer months because of the electric fan and aircon.",
    ]),
    ("Finance/Bank/bpi_statement_july.pdf", 85, "Savings Account Statement - July", [
        "Statement of account (sample). Account type: Savings. Account number: XXXX-XXXX-0000 (sample).",
        "Beginning balance: PHP 45,210.33. Total deposits: PHP 28,000.00. Total withdrawals: PHP 19,450.00. Interest earned: PHP 9.12. Ending balance: PHP 53,769.45.",
        "Transactions: 07/01 salary credit 14,000.00; 07/05 ATM withdrawal 5,000.00; 07/12 online transfer 3,450.00; 07/15 salary credit 14,000.00; 07/22 bills payment 11,000.00.",
    ]),
    ("Finance/Loans/sss_salary_loan_notes.pdf", 95, "SSS Salary Loan Notes", [
        "Requirements for an SSS salary loan: at least 36 posted monthly contributions, 6 of which in the last 12 months before the application.",
        "Loanable amount is based on the average monthly salary credit. Interest is 10 percent per year, payable in 24 monthly installments.",
        "Apply online through the My.SSS portal. Kailangan ng UMID o disbursement account na naka-enroll.",
    ]),
    ("Finance/Tax/bir_2316_notes.txt", 150, "Tax notes", [
        "BIR Form 2316 is the certificate of compensation payment and tax withheld, given by the employer every year.",
        "Check that the gross compensation, non-taxable 13th month pay and benefits, and tax withheld match your payslips.",
        "Keep a copy for loan and visa applications. Hindi na kailangang mag-file ng ITR kung pure compensation income at isang employer lang sa buong taon.",
    ]),
    ("Finance/Investments/pagibig_mp2_savings.docx", 55, "Pag-IBIG MP2 Savings Plan Notes", [
        "Ang MP2 ay voluntary savings program ng Pag-IBIG Fund na may five-year maturity. Minimum na hulog ay PHP 500.",
        "Pwedeng piliin ang annual payout ng dividends o compounded sa maturity. Mas mataas ang kita kapag compounded.",
        "Plano ko: maghulog ng PHP 1,000 kada buwan simula ngayong taon para sa emergency fund at future house down payment.",
    ]),
    ("Finance/Invoices/freelance_invoice_0042.docx", 18, "Invoice No. 0042", [
        "Bill to: Sample Bakery Co. From: Freelance web designer (sample).",
        "<table>Description|Hours|Rate|Amount\nWebsite redesign, homepage and menu pages|20|500|10000\nLogo refresh|4|500|2000\nHosting setup|2|500|1000",
        "Total due: PHP 13,000. Payment terms: 15 days via bank transfer.",
    ]),
    ("Personal/Letters/sulat_kay_lola.docx", 65, "Sulat kay Lola", [
        "Mahal kong Lola, kumusta na po kayo diyan sa probinsya? Okay naman po kami dito sa Manila, busy lang sa school at trabaho.",
        "Uuwi po kami sa Holy Week para bisitahin kayo. Si Mama po ay magpapadala ng mga gamot ninyo sa susunod na linggo.",
        "Ingat po kayo palagi at huwag kalimutang uminom ng maraming tubig. Nagmamahal, ang inyong apo.",
    ]),
    ("Personal/Resume/resume_juan_dela_cruz.docx", 200, "Juan Dela Cruz - Resume", [
        "Objective: To work as an entry-level web developer in Metro Manila.",
        "Education: Bachelor of Science in Information Technology, sample state university, 2026.",
        "Experience: Intern, sample software company. Built an inventory system using Python and MySQL and wrote unit tests.",
        "Skills: HTML, CSS, JavaScript, Python, Git, basic UI design. Languages: Filipino, English.",
    ]),
    ("Personal/Recipes/adobong_manok.txt", 170, "Adobong manok", [
        "ADOBONG MANOK",
        "Ingredients: 1 kilo manok, 1/2 cup toyo, 1/3 cup suka, 1 head bawang, 1 tsp pamintang buo, 3 dahon ng laurel.",
        "I-marinate ang manok sa toyo at bawang ng 30 minutes. Ilagay sa kaldero kasama ang marinade, laurel at paminta. Pakuluan sa mahinang apoy hanggang lumambot, mga 40 minutes.",
        "Ilagay ang suka at huwag munang haluin para hindi maging maasim. Hayaang lumapot ang sauce.",
    ]),
    ("Personal/Recipes/sinigang_na_baboy.txt", 175, "Sinigang na baboy", [
        "SINIGANG NA BABOY",
        "Ingredients: 1 kilo pork ribs, 1 pack sinigang mix o sampalok, kamatis, sibuyas, labanos, sitaw, kangkong, siling haba.",
        "Pakuluan ang baboy kasama ang kamatis at sibuyas hanggang lumambot. Idagdag ang labanos at sitaw, tapos ang sinigang mix. Huli ang kangkong.",
    ]),
    ("Personal/Travel/baguio_itinerary.pdf", 80, "Baguio Trip Itinerary", [
        "Day 1: Alis ng Manila 5 AM via bus, dating sa Baguio mga 11 AM. Check-in sa hotel malapit sa Session Road.",
        "Day 2: Burnham Park boating, Mines View Park, Good Shepherd para sa ube jam pasalubong, dinner sa night market.",
        "Day 3: Strawberry farm sa La Trinidad bago umuwi. Estimated budget per person: PHP 7,000 kasama ang bus fare.",
    ]),
    ("Personal/Travel/cebu_bohol_trip_plan.docx", 210, "Cebu and Bohol Trip Plan", [
        "Flight Manila to Cebu, then fast craft ferry to Tagbilaran, Bohol.",
        "Bohol countryside tour: Chocolate Hills, tarsier sanctuary, Loboc river cruise lunch, Baclayon church.",
        "Cebu: Magellan's Cross, Basilica del Santo Nino, lechon lunch, and Kawasan Falls canyoneering on the last day.",
    ]),
    ("Personal/Health/annual_checkup_results.txt", 125, "Checkup results", [
        "Annual physical exam (sample results, not real). Blood pressure 120/80. BMI 23.4.",
        "Total cholesterol slightly high at 210 mg/dL. Doctor advised less fried food and 30 minutes of walking daily.",
        "Follow-up blood test after three months. Fasting 10 hours before the test.",
    ]),
    ("Personal/Notes/journal_entry.txt", 8, "Journal", [
        "Grabe ang pagod ngayong linggo. Tatlong job interviews, dalawa online at isa sa Makati.",
        "Kinakabahan ako sa technical exam pero sabi ni Mama kaya ko daw. Next week malalaman ko na ang result.",
        "Note to self: matulog nang maaga at huwag mag-overthink.",
    ]),
    ("Personal/Hobbies/guitar_chords_practice.txt", 190, "Guitar practice", [
        "Guitar practice plan: 20 minutes daily.",
        "Week 1: G, C, D, Em chord changes. Week 2: strumming pattern down down up up down up. Week 3: barre chord F at Bm.",
        "Songs to learn: mga OPM classics na apat na chords lang.",
    ]),
    ("Personal/Family/family_reunion_plan.pptx", 28, "Family Reunion 2026", [
        "Dela Cruz Family Reunion 2026||December 27, sa resort sa Laguna||",
        "Food committee||Lechon, pancit, lumpia, leche flan|Bawat pamilya magdadala ng isang ulam||",
        "Games||Parlor games para sa mga bata|Videoke contest para sa matatanda|Raffle prizes||Collect PHP 500 per family for prizes.",
    ]),
    ("Personal/Pets/vet_vaccination_schedule.pdf", 105, "Vaccination Schedule for Brownie", [
        "Pet: Brownie, 4-month-old aspin puppy (sample record).",
        "6 weeks: first 5-in-1 vaccine. 9 weeks: second 5-in-1 vaccine. 12 weeks: third 5-in-1 vaccine and anti-rabies shot.",
        "Deworming every two weeks until 3 months old, then monthly. Next vet visit: anti-rabies booster after one year.",
    ]),
    ("Work/memo_hybrid_work.docx", 10, "Memo: Hybrid Work Arrangement", [
        "To all employees. Subject: Hybrid work arrangement.",
        "Simula next month, ang work from home policy ay magiging hybrid na. Kailangan pumasok sa office every Tuesday and Thursday.",
        "Ang ibang araw ay pwedeng remote basta naka-online sa Teams from 9 AM to 6 PM. Please coordinate with your team lead para sa desk reservations.",
    ]),
    ("Work/project_proposal_inventory_system.docx", 115, "Project Proposal: Inventory Management System", [
        "Background. The warehouse currently tracks stock in spreadsheets, which causes missing items and double orders.",
        "Proposed solution. A web-based inventory system with barcode scanning, low-stock alerts and monthly reports.",
        "Timeline and cost. Development will take 12 weeks with a team of three developers. Estimated cost: PHP 450,000.",
    ]),
    ("Work/q3_sales_report.pptx", 5, "Q3 Sales Report", [
        "Q3 Sales Report||July to September 2026||",
        "Highlights||Total sales up 12% compared with Q2|Best region: Central Luzon|New product line contributed 18% of revenue||",
        "Next steps||Expand distributor network in Mindanao|Run a holiday promo in November||",
    ]),
    ("Work/meeting_notes_client_kickoff.txt", 3, "Client kickoff notes", [
        "Kickoff meeting with Sample Bakery Co. for their mobile ordering app.",
        "Client wants pickup and delivery options, GCash payment, and a loyalty points feature. Launch target: first quarter next year.",
        "Action items: send wireframes by Friday, confirm the budget, schedule weekly status calls tuwing Lunes.",
    ]),
    ("Work/employee_handbook_leave_policy.pdf", 220, "Employee Handbook: Leave Policy", [
        "Section 1. Vacation leave. Regular employees earn 15 days of vacation leave per year, credited at 1.25 days per month. Vacation leave must be filed at least five working days in advance.",
        "Section 2. Sick leave. Regular employees earn 15 days of sick leave per year. A medical certificate is required for absences of more than two consecutive days.",
        "<pagebreak>",
        "Section 3. Other leaves. Maternity leave of 105 days, paternity leave of 7 days, and solo parent leave of 7 days are granted as provided by law.",
        "Section 4. Conversion. Unused vacation leave of up to 5 days may be converted to cash at the end of the year.",
        "<pagebreak>",
        "Section 5. Holidays. Work on regular holidays is paid at 200 percent of the daily rate. Work on special non-working days is paid at 130 percent.",
    ]),
    ("Downloads/barangay_clearance_requirements.pdf", 22, "Barangay Clearance Requirements", [
        "Para makakuha ng barangay clearance, magdala ng valid ID at proof of residency like a utility bill.",
        "Processing fee: PHP 100. Bukas ang barangay hall mula 8 AM hanggang 5 PM, Monday to Friday.",
        "Ang clearance ay valid for six months at kailangan ito sa job application at business permit.",
    ]),
    ("Downloads/passport_appointment_checklist.pdf", 33, "Passport Appointment Checklist", [
        "Checklist for a new passport application at the DFA consular office.",
        "Bring: printed appointment confirmation, accomplished application form, PSA birth certificate, one valid government ID with photocopy.",
        "Processing fee: PHP 950 for regular processing. Dress code: no sleeveless tops and no heavy makeup for the photo.",
    ]),
    ("Downloads/nbi_clearance_guide.txt", 48, "NBI clearance guide", [
        "How to get an NBI clearance: register online, choose an appointment schedule and branch, then pay the fee through partner payment channels.",
        "Bring the reference number and two valid IDs on the appointment day. May fingerprint scan at picture taking.",
        "Kung may HIT, babalik ka pagkatapos ng ilang araw para kunin ang clearance.",
    ]),
    ("Downloads/philhealth_member_form_notes.docx", 62, "PhilHealth Member Registration Notes", [
        "Fill out the PhilHealth Member Registration Form (PMRF) to get a PhilHealth Identification Number.",
        "Isama ang mga dependents tulad ng asawa, mga anak na below 21, at magulang na senior citizen.",
        "Submit the form at any PhilHealth local office with one valid ID.",
    ]),
    ("Downloads/scan_0012.pdf", 145, "Contract of Lease", [
        "This Contract of Lease is entered into by the Lessor, a sample property owner, and the Lessee, a sample tenant.",
        "The Lessor leases to the Lessee an apartment unit in Quezon City for a period of one year. Monthly rent is PHP 12,000, payable every 5th of the month.",
        "The Lessee shall pay a security deposit equivalent to two months rent and one month advance. Pets are not allowed. The Lessee shall not sublease the unit.",
        "Either party may terminate this lease with 30 days written notice.",
    ]),
    ("Downloads/Document1.docx", 52, "", [
        "Scholarship application essay for the CHED merit scholarship program.",
        "Ako ay panganay sa limang magkakapatid. Ang tatay ko ay tricycle driver at ang nanay ko ay nagtitinda ng gulay sa palengke.",
        "I want to become a civil engineer so I can design safer bridges and roads in our province, which floods every typhoon season.",
        "This scholarship will allow me to focus on my studies instead of working part-time to pay for tuition.",
    ]),
    ("Downloads/untitled.txt", 38, "", [
        "Car maintenance reminders",
        "Change oil every 5,000 km o every 6 months, alin man ang mauna. Last change oil: 42,300 km.",
        "Check tire pressure every week (32 psi). Replace the air filter every 20,000 km. Next PMS: 50,000 km.",
    ]),
    ("Downloads/final_final_v2.pdf", 42, "Enrollment Assessment Form", [
        "First semester enrollment assessment (sample student).",
        "Tuition fee: 21 units x PHP 1,050 = PHP 22,050. Laboratory fees: PHP 3,500. Miscellaneous fees: PHP 4,200. Total assessment: PHP 29,750.",
        "Payment schedule: 40 percent upon enrollment, the balance in three installments before the prelim, midterm and final exams.",
    ]),
    ("Downloads/notes (1).txt", 6, "", [
        "Bibilhin para sa birthday party ni Bunso:",
        "Spaghetti, hotdog, marshmallow, balloons, cake (chocolate), juice, paper plates, party hats, loot bags para sa 20 bata.",
        "Budget: PHP 5,000. Pupunta sa Divisoria sa Sabado.",
    ]),
    ("Downloads/Presentation1.pptx", 27, "Disaster Preparedness", [
        "Disaster Preparedness||Barangay seminar||",
        "Before a typhoon||Prepare a go bag with water, food, flashlight, radio and first aid kit|Monitor PAGASA advisories||",
        "During an earthquake||Duck, cover and hold|Stay away from windows|Evacuate only when the shaking stops||Demo the earthquake drill.",
        "Evacuation centers||Barangay covered court|Elementary school gym||",
    ]),
]

QUERIES: list[tuple[str, str]] = [
    ("mangrove research sa Bataan", "mangrove_research_draft.docx"),
    ("slides tungkol sa photosynthesis", "photosynthesis_lesson.pptx"),
    ("reviewer para sa mitosis at meiosis", "cell_division_reviewer.pdf"),
    ("essay about Noli Me Tangere", "rizal_noli_essay.docx"),
    ("kailan nagsimula ang Katipunan revolution", "philippine_revolution_timeline.pdf"),
    ("derivative problems", "calculus_problem_set_3.pdf"),
    ("paano kunin ang standard deviation", "statistics_notes.txt"),
    ("thesis defense reminder kahapon", "thesis_defense_reminders.txt"),
    ("related literature e-wallet students", "chapter2_rrl.docx"),
    ("kuryente bill last month", "meralco_bill_september.pdf"),
    ("water bill", "maynilad_water_bill.pdf"),
    ("resibo ng earbuds na binili online", "lazada_order_receipt.pdf"),
    ("budget para sa Pasko", "budget_disyembre.docx"),
    ("bank statement", "bpi_statement_july.pdf"),
    ("MP2 savings Pag-IBIG", "pagibig_mp2_savings.docx"),
    ("invoice for web design project", "freelance_invoice_0042.docx"),
    ("sulat para kay Lola", "sulat_kay_lola.docx"),
    ("resume ng IT graduate", "resume_juan_dela_cruz.docx"),
    ("paano magluto ng adobo", "adobong_manok.txt"),
    ("Baguio trip itinerary", "baguio_itinerary.pdf"),
    ("bakuna ng aso", "vet_vaccination_schedule.pdf"),
    ("work from home policy memo", "memo_hybrid_work.docx"),
    ("ilang araw ang vacation leave", "employee_handbook_leave_policy.pdf"),
    ("requirements sa barangay clearance", "barangay_clearance_requirements.pdf"),
    ("apartment lease contract", "scan_0012.pdf"),
    ("scholarship application essay", "Document1.docx"),
    ("kailan magpapalit ng langis ang kotse", "untitled.txt"),
    ("magkano ang tuition fee breakdown", "final_final_v2.pdf"),
    ("typhoon earthquake preparedness presentation", "Presentation1.pptx"),
    ("pdf sa Downloads tungkol sa passport", "passport_appointment_checklist.pdf"),
]

BAD_FILES = {
    "locked_payslip.pdf": "password_protected",
    "corrupted_report.pdf": "extract_failed",
    "blank_scan.pdf": "no_text",
    "broken_notes.docx": "extract_failed",
    "empty.txt": "no_text",
}
IGNORED_FILES = ["~$draft.docx", "expenses.xlsx", ".hidden_notes.txt", "download.crdownload"]


def resolve_date(spec: object, today: date) -> datetime:
    first = today.replace(day=1)
    if spec == "yesterday":
        d = today - timedelta(days=1)
    elif spec == "last_month":
        d = (first - timedelta(days=1)).replace(day=15)
    elif spec == "two_months_ago":
        d = ((first - timedelta(days=1)).replace(day=1) - timedelta(days=1)).replace(day=15)
    elif isinstance(spec, tuple) and spec[0] == "month":
        m = spec[1]
        d = date(today.year if m < today.month else today.year - 1, m, 10)
    else:
        d = today - timedelta(days=int(spec))
    return datetime.combine(d, datetime.min.time()).replace(hour=10)


def write_pdf(path: Path, title: str, paras: list[str], encrypt: str | None = None) -> None:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer

    styles = getSampleStyleSheet()
    story = [Paragraph(title, styles["Title"])] if title else []
    for p in paras:
        if p == "<pagebreak>":
            story.append(PageBreak())
        else:
            story += [Paragraph(p.replace("&", "&amp;").replace("<", "&lt;"), styles["BodyText"]), Spacer(1, 8)]
    SimpleDocTemplate(str(path), pagesize=A4, encrypt=encrypt, title=title or "Untitled").build(story)


def write_docx(path: Path, title: str, paras: list[str]) -> None:
    import docx

    d = docx.Document()
    if title:
        d.add_heading(title, level=1)
    for p in paras:
        if p.startswith("<table>"):
            rows = [r.split("|") for r in p[len("<table>"):].split("\n")]
            t = d.add_table(rows=len(rows), cols=len(rows[0]))
            for i, row in enumerate(rows):
                for j, cell in enumerate(row):
                    t.cell(i, j).text = cell
        else:
            d.add_paragraph(p)
    d.save(str(path))


def write_pptx(path: Path, title: str, slides: list[str]) -> None:
    from pptx import Presentation

    prs = Presentation()
    for s in slides:
        head, bullets, notes = (s.split("||") + ["", ""])[:3]
        slide = prs.slides.add_slide(prs.slide_layouts[1])
        slide.shapes.title.text = head
        body = slide.placeholders[1].text_frame
        items = [b for b in bullets.split("|") if b]
        body.text = items[0] if items else ""
        for b in items[1:]:
            body.add_paragraph().text = b
        if notes:
            slide.notes_slide.notes_text_frame.text = notes
    prs.save(str(path))


def write_txt(path: Path, paras: list[str]) -> None:
    path.write_text("\n\n".join(paras) + "\n", encoding="utf-8")


def build(target: Path = ROOT, today: date | None = None) -> list[Path]:
    today = today or date.today()
    target.mkdir(parents=True, exist_ok=True)
    for child in target.iterdir():
        if child.name != ".gitkeep":
            shutil.rmtree(child) if child.is_dir() else child.unlink()
    written = []
    for rel, spec, title, paras in DOCS:
        path = target / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        ext = path.suffix
        if ext == ".pdf":
            write_pdf(path, title, paras)
        elif ext == ".docx":
            write_docx(path, title, paras)
        elif ext == ".pptx":
            write_pptx(path, title, paras)
        else:
            write_txt(path, paras)
        ts = resolve_date(spec, today).timestamp()
        os.utime(path, (ts, ts))
        written.append(path)
    bad = target / "Bad"
    bad.mkdir(exist_ok=True)
    write_pdf(bad / "locked_payslip.pdf", "Payslip", ["Sample payslip, net pay PHP 18,500."], encrypt="secret123")
    (bad / "corrupted_report.pdf").write_bytes(b"%PDF-1.4\n%garbage that is not a real pdf\x00\x01\x02" * 20)
    from reportlab.pdfgen import canvas

    c = canvas.Canvas(str(bad / "blank_scan.pdf"))
    c.rect(100, 100, 300, 400)
    c.save()
    (bad / "broken_notes.docx").write_bytes(b"PK\x03\x04 this zip is truncated" * 5)
    (bad / "empty.txt").write_bytes(b"")
    (bad / "~$draft.docx").write_bytes(b"temp owner file")
    (bad / "expenses.xlsx").write_bytes(b"PK\x03\x04 not supported")
    (bad / ".hidden_notes.txt").write_text("hidden file", encoding="utf-8")
    (bad / "download.crdownload").write_bytes(b"partial")
    return written


if __name__ == "__main__":
    out = build(Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT)
    print(f"wrote {len(out)} demo documents plus {len(BAD_FILES) + len(IGNORED_FILES)} bad or ignored files")
