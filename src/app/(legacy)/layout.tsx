import type { Metadata } from "next";
import "./old.css";

export const metadata: Metadata = {
  title: "독일어 합성어 상성 진단소",
  description: "독일어 합성어를 분해하고, 영어·한국어·일본어 대응어와 짜임이 얼마나 닮았는지 퍼센트로 진단해요.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ko">
      <body>{children}</body>
    </html>
  );
}
