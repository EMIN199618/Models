import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  experimental: {
    serverActions: {
      // Model faylları böyük olur. İstehsalda bu limit aşağı salınıb,
      // yükləmə birbaşa S3-ə presigned URL ilə aparılmalıdır.
      bodySizeLimit: "500mb",
    },
  },
};

export default nextConfig;
