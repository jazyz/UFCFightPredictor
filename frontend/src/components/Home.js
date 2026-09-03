import React from "react";

export default function Home({ data }) {
  return <main className="mx-auto max-w-content px-6 py-16">{data.metrics.n} fights scored.</main>;
}
