# How an HTTP request reaches a Kubernetes app

## Hook

You press Enter. Before the page appears, four decisions are made about where your request goes. Let's follow it.

## DNS

First, the name. Your computer asks a DNS resolver, and gets back the addresses of a load balancer. That is decision one: which address.

## AWS load balancer

The load balancer is an AWS Network Load Balancer. It checks the health of every node behind it, and sends your request only to a healthy one. Decision two.

## NGINX ingress

Inside the cluster, the request reaches NGINX, the ingress controller. It reads the host and the path, and matches them to a routing rule. Decision three: which Service.

## Service to pod

But a Service is not a program. It is a stable name for a set of pods. So NGINX looks up the pods behind it, and picks one. Decision four.

## Response and recap

The pod answers, and the response travels back the same way. One request. Four decisions. All before the page appears.
