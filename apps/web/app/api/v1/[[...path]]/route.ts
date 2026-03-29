import { NextRequest, NextResponse } from "next/server";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

function apiUpstream(): string {
  return process.env.API_INTERNAL_URL || "http://127.0.0.1:8000";
}

function buildTarget(pathSegments: string[], search: string): string {
  const sub = pathSegments.length ? pathSegments.join("/") : "";
  return `${apiUpstream()}/api/v1/${sub}${search}`;
}

async function proxy(req: NextRequest, pathSegments: string[]): Promise<Response> {
  const targetUrl = buildTarget(pathSegments, req.nextUrl.search);
  const hdrs = new Headers(req.headers);
  hdrs.delete("host");
  hdrs.delete("connection");

  const method = req.method.toUpperCase();
  if (method === "GET" || method === "HEAD") {
    const res = await fetch(targetUrl, { method: req.method, headers: hdrs, redirect: "manual" });
    return new NextResponse(res.body, {
      status: res.status,
      statusText: res.statusText,
      headers: res.headers,
    });
  }

  /* Буфер целиком: стриминг + duplex в Node часто ломает multipart — FastAPI не видит POST. */
  const body = await req.arrayBuffer();
  const res = await fetch(targetUrl, {
    method: req.method,
    headers: hdrs,
    body: body.byteLength ? body : undefined,
    redirect: "manual",
  });
  return new NextResponse(res.body, {
    status: res.status,
    statusText: res.statusText,
    headers: res.headers,
  });
}

export async function GET(req: NextRequest, ctx: { params: Promise<{ path?: string[] }> }) {
  const { path } = await ctx.params;
  return proxy(req, path ?? []);
}

export async function POST(req: NextRequest, ctx: { params: Promise<{ path?: string[] }> }) {
  const { path } = await ctx.params;
  return proxy(req, path ?? []);
}

export async function PATCH(req: NextRequest, ctx: { params: Promise<{ path?: string[] }> }) {
  const { path } = await ctx.params;
  return proxy(req, path ?? []);
}

export async function PUT(req: NextRequest, ctx: { params: Promise<{ path?: string[] }> }) {
  const { path } = await ctx.params;
  return proxy(req, path ?? []);
}

export async function DELETE(req: NextRequest, ctx: { params: Promise<{ path?: string[] }> }) {
  const { path } = await ctx.params;
  return proxy(req, path ?? []);
}
