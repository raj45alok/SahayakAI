// File: api/saveUser.js
const { DynamoDBClient, PutItemCommand } = require("@aws-sdk/client-dynamodb");

module.exports = async function handler(req, res) {
  // Only allow POST requests
  if (req.method !== "POST") {
    return res.status(405).json({ error: "Method not allowed" });
  }

  try {
    // Parse request body safely
    const { firebaseUser, userType, additionalData } = 
      typeof req.body === "string" ? JSON.parse(req.body) : req.body;

    // Validate required fields
    if (!firebaseUser?.uid || !userType) {
      return res.status(400).json({ error: "Missing required user fields" });
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
    const userId = userType === "student"
      ? `STU-${require('crypto').randomUUID().slice(0, 8)}`
      : `TCH-${require('crypto').randomUUID().slice(0, 8)}`;

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

    // Respond success
    return res.status(200).json({ success: true, userId });
  } catch (err) {
    console.error("❌ Error saving user:", err);
    return res.status(500).json({ error: err.message || "Internal Server Error" });
  }
};