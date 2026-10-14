// Initialize replica set rs0 with mongo1:27017
try {
  const status = rs.status();
  if (status.ok === 1) {
    console.log("Replica set already initialized.");
  }
} catch (e) {
  console.log("Initializing replica set rs0 with member mongo1:27017...");
  const res = rs.initiate({
    _id: "rs0",
    members: [{ _id: 0, host: "mongo1:27017" }]
  });
  console.log("rs.initiate result:", JSON.stringify(res));
}
