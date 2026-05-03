"""
Verbatim contract text from the legacy Drive PDF templates
(VRH 2025 LEGAL.pdf, Mike Mancini 2025.pdf, Jayden Marcos 2025.pdf,
Danny Steele 2025.pdf — all 4 share identical legal text).

This is the source of truth. The Hub imports a mirrored TS copy in
hub/lib/compliance-contract.ts; tests/test_contract_parity.py keeps
the two files in sync.

Typos preserved verbatim as they appear in the legacy PDFs:
  - "Servics" (Section 1) — sic in original
  - "<YOUR JURISDICTION>" (Section 11) — sic in original; never filled
  - "(“ICCC)"          (Section 11) — sic, missing close-quote
  - "operator received"     (Perjury)   — sic, lowercase
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ContractSection:
    id: str
    heading: str
    body: str


# ─── Document title + intro ──────────────────────────────────────────────────

CONTRACT_TITLE = "Model Services Agreement and Release"

CONTRACT_INTRO = (
    "This Model Services Agreement and Release (this “Agreement”), is "
    "between the person signing as Model below (“Model”) and Eclatech LLC "
    "(Company & Producer)."
)

# ─── Numbered sections (Model Services Agreement) ────────────────────────────

AGREEMENT_SECTIONS: tuple[ContractSection, ...] = (
    ContractSection(
        id="services",
        heading="1. Services",
        body=(
            "Model will provide services as an actor and/or model in a video/VR "
            "production for Producer and other related promotional and commercial "
            "productions relating thereto (the “Production”) and agrees to "
            "provide those services until the completion of the Production. Model "
            "shall perform these services in good faith and to the Model’s "
            "best ability, in the manner and at the times and places directed by "
            "Producer, all of the services required by Producer hereunder, "
            "including, but not limited to, pre-production services, services in "
            "connection with the principal photography of the Production, "
            "post-production services, including retakes, and such other services "
            "as are customarily performed or required to be performed by an actor "
            "in a motion picture/VR production. Model shall comply with all "
            "reasonable directions, requests, rules and regulations of Producer in "
            "connection herewith, whether or not the same involves matters of "
            "artistic taste or judgment. Each of Model’s obligations under "
            "this paragraph, Model’s other obligations hereunder, and all "
            "other services performed for Producer and the Production, shall be "
            "defined as the “Servics.” Model acknowledges that the "
            "engagement is a one-time engagement with no representation or promise "
            "that Model will be entitled to any other work from Producer. "
            "Notwithstanding the foregoing, if Model performs in any other "
            "production for Producer, such performance shall be subject to this "
            "Agreement.\n\n"
            "Model acknowledges and understands that the Production may be made "
            "available on the Internet and any and all other mediums by Producer "
            "and/or its affiliates and may be viewed and/or downloaded by the "
            "general public."
        ),
    ),
    ContractSection(
        id="compensation",
        heading="2. Compensation",
        body=(
            "Producer shall pay Model the agreed compensation in consideration of "
            "Model’s performance of the Services (the “Compensation”). "
            "The Compensation shall be paid in accordance with Producer’s "
            "standard practices as may be established or modified from time to "
            "time. Model shall complete and execute certain tax documentation as "
            "required by Producer, and Producer may withhold all Compensation "
            "until such time as Model submits these documents to Producer."
        ),
    ),
    ContractSection(
        id="acknowledgement",
        heading="3. Acknowledgement and Waiver; Explicit/Sexual Activities",
        body=(
            "Model understands and agrees to the following and waives all claims "
            "that may relate or arise from the following: (a) the Services and "
            "the Production may be utilized in conjunction with sexually graphic "
            "or explicit material; (b) any sex involving Model may be simulated "
            "or actual; (c) Producer shall have no obligation to release or "
            "complete the Production, or to ever utilize the Services; (d) Model "
            "shall have no right to inspect or approve the finished Production, "
            "or the use of the Services in the Production or other work; (e) "
            "Model, the Services and/or the Production may be subject to "
            "blurring, distortion, alteration, retouching, optical illusion and "
            "therefore the Production and/or the use of the Services may hold "
            "Model in a false or unfavorable light, whether intentional or "
            "otherwise; (f) Model may be engaging in sexual acts with others "
            "that will be of an explicit or dangerous nature (including, "
            "potentially, oral sex, anal sex, group sex or otherwise) and that "
            "Model is engaging in all such acts voluntarily, knowing that Model "
            "has the right to stop at any time without penalty; (g) Producer may, "
            "by the use of the services of others, “double” or "
            "“dub” any acts, poses, plays, appearances, voices or "
            "sound effects attributed to, or to be attributed to, the Model in "
            "such circumstances as Producer, in its sole and complete discretion, "
            "shall deem necessary or desirable; (h) Producer may require Model "
            "to wear particular clothing, costumes, accessories and/or makeup "
            "reasonably selected by Producer and may prohibit Model from wearing "
            "any apparel bearing a logo, trademark or copyright without the "
            "express, prior consent of Producer; (i) Producer may require Model "
            "to use a condom."
        ),
    ),
    ContractSection(
        id="grant_of_rights",
        heading="4. Grant of Rights",
        body=(
            "(a) Model hereby grants and assigns to Producer the full rights and "
            "license to use Model’s likeness, performance and any other "
            "content, expression or otherwise arising from the Services, "
            "including, without limitation, the following perpetual and "
            "exclusive rights: (i) to photograph or otherwise reproduce all or "
            "any part of Model’s performances, acts, poses, play and "
            "appearances of every kind and nature made or done by Model in "
            "connection with the Services and/or the Production; (ii) to record "
            "or otherwise reproduce Model’s voice and all musical, "
            "instrumental or other sound effects produced by Model in connection "
            "with the Services and/or the Production and reproduce, issues, sell "
            "and transmit the same; (iii) to exhibit, sell, assign, transmit and "
            "reproduce and license others to do the foregoing, whether by means "
            "of, without limitation, motion pictures, still camera photographs, "
            "radio, television, televised motion pictures, video discs, video "
            "cassettes, video tapes, printing, or any other means now known or "
            "unknown; (iv) to use the Services in connection with the "
            "advertising and exploitation of the Production, including, without "
            "limitation, the creation of previews and trailers, one-sheet, "
            "flyers, catalogs, and covers or wrappers of sound track records, "
            "discs, tapes and/or cassettes, and in connection with the sale of "
            "any by-products or merchandising relating to the Production, and "
            "any characters, themes, lot or other elements or rights therein "
            "contained; (v) to use the Services, or any part thereof, as a "
            "portion of a motion picture or other work other than the "
            "Production, and for the advertising thereof, and in connection with "
            "the sale of any by-products or merchandise relating thereto, and to "
            "reproduce and/or transmit the same by and in any media; (vi) to "
            "cut, edit, add to, subtract from, arrange, rearrange, shorten and "
            "revise the Services and the Production in any manner as Producer "
            "may, in its sole and complete discretion, determine and, from time "
            "to time, to change the title thereof. Without limiting the "
            "foregoing, Model acknowledges and agrees that Model is hereby "
            "assigning to Producer all rights and title to any films, "
            "recordings, photographs and other expressions, and the results of "
            "the Services (including performances performed by Model in "
            "providing the Services) to Producer.\n\n"
            "(b) Model hereby grants Producer the perpetual rights to exploit "
            "and to license others to exploit, Model’s name and biography "
            "and reproductions of Model’s physical likeness and/or voice "
            "for the purpose of advertising and exploiting any product embodying "
            "the Services and the right to use any of the rights herein granted "
            "for commercial advertising or publicity (including endorsements) in "
            "connection with any product, commodity or services manufactured, "
            "distributed or offered by Producer.\n\n"
            "(c) Model grants Producer the right to use Model’s stage name, "
            "and any other stage names that Model has used in the past or may "
            "use in the future, including those which may be trademarked.\n\n"
            "(d) Model shall sign, execute and deliver any and all documents or "
            "instruments, including declarations, invention assignments and "
            "copyright assignments, and any and all other applications in "
            "whatsoever countries and will take any other action which Producer "
            "shall deem necessary to perfect trademark, copyright or patent "
            "rights with respect to the Services and the likeness and "
            "performances of Model, which relate to or arise out of the "
            "Services, or to otherwise protect Producer’s proprietary "
            "interests.\n\n"
            "(e) To the extent that Model retains any interest in any likeness, "
            "performance, recording or other production or reproduction granted "
            "hereunder to Producer or created as part of the Services, Model "
            "hereby grants and assigns to Producer all rights of any nature in "
            "and to the same on a royalty-free basis throughout the universe in "
            "perpetuity. To the maximum extent permitted under applicable law, "
            "Model hereby waives any “moral rights” or any analogous "
            "rights, however denominated, in every jurisdiction. Model agrees "
            "that all works produced hereunder are and shall be deemed "
            "“works made for hire.”"
        ),
    ),
    ContractSection(
        id="confidentiality",
        heading="5. Confidentiality",
        body=(
            "Model shall not take any photos, videos or any other form of "
            "recording of the Production. Model shall not distribute any photos, "
            "videos or any other form of recording of the Production. Model shall "
            "treat the Production as confidential prior to its general "
            "distribution (in the discretion of Producer) and shall not disclose "
            "the outcome, story line or specifics of the production prior to its "
            "general distribution."
        ),
    ),
    ContractSection(
        id="testing",
        heading="6. Testing",
        body=(
            "Model must provide Producer with documentation confirming that Model "
            "has been tested for H.I.V. and other industry standard tested "
            "sexually transmitted diseases within 14 days prior to Model’s "
            "performance of any sexual acts and that show that Model is not "
            "infected with any such diseases. Model may inspect the same "
            "documentation of any co-performer of Model and should notify Producer "
            "of any reasonable doubts Model may have as to that documentation. "
            "Model understands that Model is aware of the risks of contracting "
            "sexually transmitted diseases or other diseases through other means, "
            "and expressly and in perpetuity agrees to assume any and all risks of "
            "contracting any sexually transmitted disease or other disease while "
            "engaged in the Services and/or performing for the Production. Model "
            "hereby releases, indemnifies and shall hold Producer harmless against "
            "any claims that Model contracted a sexually transmitted disease or "
            "other disease or if Model passed a sexually transmitted disease or "
            "other disease onto a co-performer or any other party."
        ),
    ),
    ContractSection(
        id="no_employment",
        heading="7. No Employment or Benefits",
        body=(
            "Model acknowledges that Model is not an employee of Producer, but an "
            "independent contractor (being self-employed). Model acknowledges that "
            "Model is not entitled to any benefits from Producer, including group "
            "insurance, liability insurance, disability insurance, paid vacation, "
            "sick leave or other leave, retirement plan, health plan, premium "
            "“overtime” pay, or any other benefit. Should Model be "
            "deemed to be entitled to any benefits or employee rights from "
            "Producer by operation of law or otherwise, Model expressly waives "
            "all such benefits. As an independent contractor, Model will look "
            "exclusively to himself/herself to: (a) pay or withhold as required, "
            "federal, state, and local employment taxes or other taxes or "
            "payments (Model will provide Producer with suitable evidence of "
            "payment upon request); (b) provide Worker's Compensation coverage to "
            "the extent required by law; (c) pay the premium “overtime” "
            "rate for overtime hours if required. Producer shall not bear any "
            "responsibility to pay or withhold any of these taxes or other "
            "payments. In the event any individual or entity brings or threatens "
            "to bring a claim against Producer related to the status, acts or "
            "omissions of Model, Model agrees to cooperate with Producer. "
            "Model’s cooperation shall include providing accurate factual "
            "information to support Model’s representations of Model’s "
            "status as being self-employed. Producer assumes no responsibility "
            "for paying any taxes, withholding, banking commissions or currency "
            "fees on Model’s behalf and Model agrees and acknowledges that "
            "Model assumes complete and sole responsibility for any taxes, "
            "withholding, banking commissions or currency fees owed as a "
            "consequence of Model’s Services. However, if Producer is "
            "required to deduct, withhold, or otherwise pay any taxes or make any "
            "withholding under any provision of applicable law, then Producer may "
            "deduct and withhold from Model an amount equal to any such "
            "deduction, withholding or taxes and all such amounts shall be "
            "treated as if paid under this Agreement."
        ),
    ),
    ContractSection(
        id="covenants",
        heading="8. Additional Covenants, Representations and Warranties",
        body=(
            "Model covenants, represents and warrants as follows: (a) Model is in "
            "good health and has no medical, physical or emotional conditions "
            "that may interfere with the Services; (b) Model will not be under "
            "the influence of any medication or drugs that will impair "
            "Model’s ability to engage in the Services or that may impair "
            "Model’s judgment while engaging in the Services; (c) "
            "Model’s provision of the Services is not subject to any union "
            "or guild collective bargaining agreement; (d) Model is not bound by "
            "any agreement or other existing or previous business relationship "
            "which conflicts with or prevents the full performance of "
            "Model’s duties and obligations to Producer hereunder; and (e) "
            "Model’s provision of the Services will not violate or infringe "
            "upon any rights of any third party and will not cause Model to be "
            "in breach or violation of any agreements to which Model is a party."
        ),
    ),
    ContractSection(
        id="remedies",
        heading="9. Remedies; Limitations of Liabilities",
        body=(
            "Model agrees that any breach of this Agreement by Model would cause "
            "irreparable damage to Producer. Producer shall have, in addition to "
            "any and all remedies of law, the right to an injunction, specific "
            "performance or other equitable relief to prevent any violation of "
            "Model’s obligations hereunder, without the necessity of posting "
            "a bond. Model shall defend, indemnify and hold harmless the Producer "
            "(as well as its affiliates, agents, successors and assigns) from any "
            "and all claims, actions, damages, losses, liabilities, costs, "
            "attorney’s fees, expenses, injuries or causes of action arising "
            "from or related to Model’s breach or alleged breach of this "
            "Agreement. Under no circumstances shall Producer be liable to Model "
            "for any indirect, incidental, special, consequential, punitive or "
            "exemplary damages arising from the transactions contemplated by this "
            "Agreement, even if it has been advised of the possibility of such "
            "damages."
        ),
    ),
    ContractSection(
        id="miscellaneous",
        heading="10. Miscellaneous",
        body=(
            "Any waiver by Producer of a breach of any provision of this "
            "Agreement shall not operate or be construed as a waiver of any "
            "subsequent breach hereof. If one or more of the provisions contained "
            "in this Agreement shall for any reason be held to be excessively "
            "broad as to scope, activity or subject matter so as to be "
            "unenforceable at law, such provision(s) shall be construed and "
            "reformed by the appropriate judicial body by limiting and reducing "
            "it (or them), so as to be enforceable to the maximum extent "
            "compatible with the applicable law as it shall then appears. "
            "Producer shall have the right to assign this Agreement to its "
            "successors and assigns and all covenants and agreements hereunder "
            "shall inure to the benefit of and be enforceable by the successors "
            "of Producer. Model may not assign this Agreement. Model "
            "acknowledges the personal nature of this Agreement as it relates to "
            "Model. Any assignee to the copyright in the Production is a "
            "third-party beneficiary of this Agreement. This Agreement represents "
            "the entire agreement of the Parties. Any modification of this "
            "Agreement must be in writing and signed by both Parties. The "
            "Agreement may be executed in counterparts, each of which will be "
            "deemed an original and all of which together will constitute one and "
            "the same. An electronic (i.e. PDF, DocuSign, EchoSign) signature by "
            "a Party shall constitute valid and binding due execution of this "
            "Agreement by such Party and certified electronic signatures of the "
            "parties shall be considered to be originals. A copy of this "
            "Agreement can be used for any and all purposes hereunder, including "
            "the enforcement of a Party’s rights hereunder."
        ),
    ),
    ContractSection(
        id="governing_law",
        heading="11. Governing Law; Jurisdiction; Arbitration",
        body=(
            "This Agreement shall be governed by, and construed in accordance "
            "with, the laws of <YOUR JURISDICTION>, excluding its conflict of "
            "laws rules. MODEL AGREES THAT MODEL MAY BRING CLAIMS ONLY IN "
            "MODEL’S INDIVIDUAL CAPACITY AND NOT AS A PLAINTIFF OR CLASS "
            "MEMBER IN ANY PURPORTED CLASS OR REPRESENTATIVE ACTION. If any "
            "dispute concerning interpretation or application of this Agreement "
            "arises which cannot be resolved by mutual discussion between the "
            "Parties, then each of the Parties agrees that all disputes arising "
            "out of or in connection with the present contract shall be submitted "
            "to the International Court of Arbitration of the International "
            "Chamber of Commerce (“ICCC) and shall be finally settled under "
            "the Rules of Arbitration of the International Chamber of Commerce by "
            "a single arbitrator appointed in accordance with the said Rules. "
            "Parties may agree on submitting their dispute to any other "
            "arbitration service. The Parties acknowledge that by agreeing to "
            "this arbitration procedure, each waives the right to resolve any "
            "such dispute through a trial by judge, jury or administrative "
            "proceeding. Parties agree that this promise to arbitrate covers any "
            "dispute arising out of or relating to this Agreement, any claims "
            "concerning the validity, interpretation, effect or violation of this "
            "Agreement. The arbitrator, and not a court, shall be authorized to "
            "determine whether provisions of this Section apply to a dispute, "
            "controversy or claim sought to be resolved in accordance with this "
            "arbitration procedure, and the arbitrator shall issue a written "
            "arbitration decision which includes the essential findings and "
            "conclusions and a statement of the award. Nothing in this paragraph "
            "shall prevent either Party from seeking injunctive relief in court "
            "to prevent irreparable harm pending the conclusion of any such "
            "arbitration, in accordance with applicable law. The arbitration "
            "shall be conducted in Limassol, Cyprus, unless otherwise mutually "
            "agreed. The language used in the arbitral proceedings will be "
            "English.\n\n"
            "Model hereby agrees that as part of the consideration for these "
            "terms, Model is hereby waiving any right Model may have to a trial "
            "by jury for any dispute between the Parties arising from or "
            "relating to this Agreement, the Services or the Production. This "
            "provision shall be enforceable even in the case that the "
            "arbitration provisions or any other provisions of this Agreement "
            "are waived."
        ),
    ),
)

# ─── Witness statement (final paragraph before signatures) ───────────────────

WITNESS_STATEMENT = (
    "Model represents that Model has read, understands and agrees to the terms "
    "of this Agreement, has had an opportunity to ask any questions and to "
    "seek the assistance of an attorney regarding their legal effect, and is "
    "not relying upon any advice from Producer."
)

EXECUTION_LINE = (
    "IN WITNESS WHEREOF, the undersigned Model and Producer have executed this "
    "Agreement as of Effective Date."
)

# ─── 18 U.S.C. § 2257 Performer Names Disclosure (page 6 of legacy PDF) ──────

DISCLOSURE_HEADING = "PERFORMER NAMES DISCLOSURE STATEMENT"

DISCLOSURE_STATEMENT = (
    "I understand that the producer of the production I am participating in "
    "examined a government-issued picture identification card to determine my "
    "legal name and date of birth. Furthermore, I understand that the producer "
    "is required to obtain from me a record of all my names and aliases to "
    "thereafter be maintained in the records of the producer as required by "
    "law. I hereby present this document with the foregoing information and "
    "with the documentation being provided to the Producer concurrently "
    "herewith, in accordance with the referenced laws."
)

DOCUMENTS_PROVIDED_HEADING = (
    "I HEREBY AM PROVIDING THE FOLLOWING DOCUMENTS CONCURRENTLY HEREWITH:"
)

DOCUMENTS_PROVIDED_LIST: tuple[str, ...] = (
    "1. Copies of both sides of government-issued photo identification",
    "2. Picture of me holding my government-issued photo identification near my face",
    "3. Any further documentation requested by the producer to confirm my age and identity",
)

# ─── Data-processing consent (page 7) ────────────────────────────────────────

DATA_CONSENT = (
    "Model consents to the Producer holding and processing information about "
    "him/her for legal, remuneration, administrative and management purposes. "
    "Model hereby explicitly consents to the holding and processing of the "
    "following personal and sensitive personal data: (a) information submitted "
    "on this form, gender information’s health records and any medical "
    "reports; (b) information required to execute services under this "
    "Agreement; (c) information relating to criminal proceedings in which he "
    "has been or is involved (to comply with legal requirements and "
    "obligations to third parties or/and similar). Model agrees that Producer "
    "may make such information available to any affiliate, advisers, insurers, "
    "benefits providers, payroll administrators, regulatory authorities, "
    "governmental or quasi-governmental organisations and third parties needed "
    "for monetization of this agreement. Model hereby consents to the "
    "transfer of such information outside the European Economic Area. Model "
    "acknowledges that such countries may not have laws in place to adequately "
    "protect Model’s data and privacy. The data stored on the basis of "
    "public interest shall be stored permanently or as required by law, other "
    "that shall be deleted once no longer needed in accordance with applicable "
    "regulation. Model has the right to withdraw consent, whereas such consent "
    "may influence on future providing of the Services."
)

# ─── Perjury statement (final paragraph before second signature) ─────────────

PERJURY_STATEMENT = (
    "I hereby state under the pain and penalties of perjury that the following "
    "information is true, correct and complete to the best of my knowledge and "
    "that the provided documentation is a true, correct, complete, valid and "
    "unexpired government issued photo identification card that was not "
    "obtained by fraud or deception of any kind. I further state under the "
    "pains and penalties of perjury that I am over eighteen (18) years of age, "
    "or, if the age of majority in my legal jurisdiction is greater than "
    "eighteen (18) years of age, then I am over such age. I further affirm, "
    "under the pains and penalties of perjury, that the names and aliases I "
    "have listed on this document are all of the names and aliases that I "
    "have ever used or by which I have ever been known."
)

INDEMNITY_STATEMENT = (
    "Without limiting or otherwise prejudicing the provisions of any other "
    "agreement I may have with the producer, I agree to indemnify and hold the "
    "producer harmless for my breach of any covenant, representation or "
    "warranty in this document or the documentation being provided herewith, "
    "including, without limitation, if I provide any false information or "
    "documents to the producer. I also hereby agree to release the producer "
    "and its affiliates from any liability arising out of my breach of any "
    "covenant, representation or warranty in this document, including, "
    "without limitation, if I provide any false information or documents to "
    "the producer. I acknowledge that operator received this document and the "
    "documents provided herewith in good faith and that the producer took a "
    "good faith effort to ensure that I was in compliance with the "
    "requirements herein."
)

# ─── Producer details (filled into the rendered PDF) ─────────────────────────

PRODUCER_NAME = "Eclatech LLC"
