import client from "./client";

export async function postSmart(formData) {
  try {
    const { data } = await client.post("/solar/smart", formData, {
      headers: { "Content-Type": "multipart/form-data" },
    });
    return data;
  } catch (err) {
    throw new Error(err?.response?.data?.detail || "Failed to fetch Smart result");
  }
}

export async function postManual(fields) {
  try {
    const params = new URLSearchParams(fields);
    const { data } = await client.post("/solar/manual", params, {
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
    });
    return data;
  } catch (err) {
    throw new Error(err?.response?.data?.detail || "Failed to fetch Manual result");
  }
}
