export function validatePositive(v) {
  const num = Number(v);
  return typeof num === "number" && !isNaN(num) && num > 0;
}
