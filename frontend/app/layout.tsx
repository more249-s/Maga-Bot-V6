
export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ar" dir="rtl">
      <body className="bg-neutral-950 text-neutral-100">{children}</body>
    </html>
  );
}
