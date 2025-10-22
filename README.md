# 📘 Sahayak AI

**An AI-powered Classroom Assistant for Grades 6–8**
Empowering teachers and students through automation, AI enrichment, and intelligent scheduling using **AWS Bedrock**, **Lambda**, and **Firebase**.

🔗 **Live Demo:** [sahayak-ai-sigma.vercel.app](https://sahayak-ai-sigma.vercel.app/)
▶️ **YouTube Demo:** [Watch on YouTube](https://youtu.be/YFTC39W-VJA)

---

## 🎯 Overview

Sahayak AI is a cloud-based educational assistant designed for **Indian middle schools**. It helps teachers automate lesson scheduling, worksheet generation, assignment evaluation, and student performance analysis — all powered by AWS and AI agents.

The project was developed as part of a hackathon to demonstrate **autonomous AI behavior** using AWS services and Bedrock, showcasing real-world educational impact.

---

## 🧩 Core Features

### 1. 🗓 Scheduled Content Delivery

* Teachers upload content and define duration.
* AI agent (EventBridge + Bedrock) enriches material with YouTube links.
* One subject delivered daily (~40–60 mins workload).
* Students receive email notifications on delivery.

**AWS Services:** Lambda, S3, DynamoDB, EventBridge, Bedrock, SES/Nodemailer.

---

### 2. 🧠 Worksheet Generation

* Teachers upload files + instructions (difficulty, question type, count).
* Bedrock generates MCQs, short/long questions aligned with NCERT.
* Output as Word/PDF, stored in S3 for download.

**AWS Services:** Lambda, S3, DynamoDB, Bedrock.

---

### 3. 🧾 Assignment Scheduling & Evaluation

* Teachers schedule assignments stored in DynamoDB.
* Students submit via Google Forms/Docs stored in S3.
* Lambda parses responses, Bedrock evaluates answers.
* Grades stored in DynamoDB and emailed to parents.

**AWS Services:** Lambda, Bedrock, S3, DynamoDB, SES/Nodemailer.

---

### 4. 🪄 Content Enhancer

* Teachers upload notes (Word/PDF).
* Bedrock enriches content: simplify, elaborate, or visualize.
* Returns editable enhanced content.

**AWS Services:** Lambda, Bedrock, S3.

---

### 5. 📊 Student Performance Analytics

* Aggregates test and assignment data from DynamoDB.
* Displays per-student and per-class trends.

**AWS Services:** DynamoDB, Lambda, S3.

---

## 🌟 Mini Features

1. **Parent Reports** – Nodemailer sends weekly performance summaries.
2. **Doubt Solver** – Students submit questions → Bedrock answers → unresolved queries flagged for teacher review.
3. **Automated Notifications** – EventBridge + Lambda trigger email alerts for every scheduled upload, assignment, or test.

---

## 🧱 System Architecture

```
Frontend (React + Firebase Auth)
        ↓
API Gateway (REST Endpoints)
        ↓
Lambda Functions (Node.js / Python)
        ↓
DynamoDB ←→ S3 ←→ Bedrock
        ↓
SES/Nodemailer
```

### 🔹 Key AWS Components

| Service            | Purpose                                             |
| ------------------ | --------------------------------------------------- |
| **Lambda**         | Executes AI agents, API logic, and automation flows |
| **EventBridge**    | Triggers autonomous content scheduling              |
| **S3**             | Stores study packs, worksheets, and assignments     |
| **DynamoDB**       | Metadata and user/assignment tracking               |
| **Bedrock**        | AI enrichment, worksheet & grading generation       |
| **SES/Nodemailer** | Notifications and parent reports                    |
| **Firebase Auth**  | Authentication for teachers and students            |

---

## 🧠 Autonomous Agent Behavior

Sahayak AI operates autonomously once teachers upload content:

1. **Schedules delivery** using EventBridge.
2. **Enriches** with YouTube learning links.
3. **Notifies** students via email.
4. **Evaluates** submissions automatically.
5. **Generates** reports without manual intervention.

This behavior aligns with the hackathon requirement for *AI-driven autonomy*.

---

## 🧰 Tech Stack

**Frontend:** React.js + Tailwind CSS + Firebase Auth
**Backend:** AWS Lambda (Node.js), API Gateway, Bedrock SDK
**Database:** DynamoDB
**Storage:** AWS S3
**AI/ML:** AWS Bedrock (Claude, Titan)
**Email/Notifications:** AWS SES / Nodemailer
**Integration:** Google Forms + YouTube Data API

---

## ⚙️ Setup & Deployment

### 🔧 Prerequisites

* Node.js 18+
* AWS CLI configured
* Firebase project + service credentials
* IAM permissions for Lambda, S3, DynamoDB, EventBridge, SES

### 🪜 Steps

#### 1. Clone Repository

```bash
git clone https://github.com/<your-username>/sahayakai.git
cd sahayakai
```

#### 2. Install Dependencies

```bash
npm install
```

#### 3. Environment Configuration

Create a `.env` file in the root with:

```bash
AWS_REGION=us-east-1
S3_BUCKET=sahayak-study-packs
FIREBASE_PROJECT_ID=<your_project_id>
FIREBASE_PRIVATE_KEY=<your_private_key>
FIREBASE_CLIENT_EMAIL=<your_service_email>
SMTP_USER=<your_email>
SMTP_PASS=<your_app_password>
```

#### 4. Run Frontend (React)

```bash
npm run dev
```

#### 5. Deploy Lambda Functions

You can deploy manually or use the Serverless Framework:

```bash
cd Lambda-Functions
serverless deploy
```

#### 6. Setup EventBridge Rules

Schedule rules for autonomous content delivery:

```bash
aws events put-rule --schedule-expression "rate(1 day)" --name sahayak-daily-delivery
```

---

## 🧪 Testing & Demo Preparation

| Component       | Test Method                                                |
| --------------- | ---------------------------------------------------------- |
| Content Upload  | Upload sample file → Check S3 + DynamoDB entry             |
| Worksheet Gen   | Run Lambda `generateWorksheet` manually → Check output doc |
| Assignment Eval | Submit Google Form → Observe Bedrock evaluation JSON       |
| Notifications   | Check student & parent email delivery                      |
| Dashboard       | View updated metrics in the app                            |

### 💡 Demo Tips

* Pre-cache Bedrock outputs (to save credits)
* Keep fallback worksheets/videos ready
* Showcase autonomous scheduling visually

---

## 🖼️ Screenshots

Screenshots from the working app are available in the `/screenshots` folder.

---

## 🔒 Security & Best Practices

* Store Firebase and SMTP credentials in **AWS Secrets Manager**.
* Validate Firebase tokens in every Lambda request.
* Minimize student PII (hash IDs).
* Enable CloudWatch logging for all functions.
* Implement CORS for API Gateway securely.

---

## 🚀 Future Enhancements

* Personalized student recommendations
* Multilingual support (Hindi/English)
* AI-based plagiarism detection for assignments

---

## 🏁 Acknowledgements

Developed for the **AWS AI Hackathon** to showcase educational impact through AI autonomy.

**Contributors:** Team Sahayak AI
**Tech Stack:** AWS Bedrock · DynamoDB · Lambda · EventBridge · React · Firebase

---

> ✨ *"Sahayak AI — Your Intelligent Teaching Partner."*
