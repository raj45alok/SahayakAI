// File: api/saveUser.js
import crypto from "crypto";
import { DynamoDBClient, PutItemCommand } from "@aws-sdk/client-dynamodb";

export default async function handler(req, res) {
  // Only allow POST requests
  if (req.method !== "POST") {
    return res.status(405).json({ error: "Method Not Allowed" });
  }

  try {
    // Parse request body safely
    const { firebaseUser, userType, additionalData } =
      typeof req.body === "string" ? JSON.parse(req.body) : req.body;

    // Validate required fields
    if (!firebaseUser?.uid || !userType) {
      return res.status(400).json({ error: "Missing required fields" });
    }

    // Create DynamoDB client
    const client = new DynamoDBClient({
      region: process.env.AWS_REGION,
      credentials: {
        accessKeyId: process.env.AWS_ACCESS_KEY_ID,
        secretAccessKey: process.env.AWS_SECRET_ACCESS_KEY,
      },
    });

    // Generate user ID
    const userId =
      userType === "student"
        ? `STU-${crypto.randomUUID().slice(0, 8)}`
        : `TCH-${crypto.randomUUID().slice(0, 8)}`;

    // Prepare item for DynamoDB
    const params = {
      TableName: process.env.DYNAMO_USERS_TABLE,
      Item: {
        userId: { S: userId },
        firebaseUid: { S: firebaseUser.uid },
        role: { S: userType },
        name: { S: firebaseUser.displayName || additionalData?.name || "" },
        email: { S: firebaseUser.email },
        phone: { S: additionalData?.phone || "" },
        createdAt: { S: new Date().toISOString() },
      },
    };

    // Store in DynamoDB
    await client.send(new PutItemCommand(params));

    console.log("✅ User saved successfully:", userId);
    return res.status(200).json({ success: true, userId });
  } catch (err) {
    console.error("❌ Error saving user:", err);
    return res
      .status(500)
      .json({ error: err.message || "Internal Server Error" });
  }
}
