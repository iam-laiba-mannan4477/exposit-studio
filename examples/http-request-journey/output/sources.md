# Sources for How an HTTP request reaches a Kubernetes app

Arrangement depicted: A public DNS name that resolves to an AWS Network Load Balancer with instance targets (the cluster's worker nodes) across three Availability Zones; the F5 NGINX Ingress Controller running in the cluster; one Ingress rule for host shop.example.com and path /cart pointing at a Service named cart; three pods behind that Service. NGINX balances directly to pod addresses, which is that controller's default.

- **c1** A Network Load Balancer has a DNS name that resolves to the IP addresses of its load balancer nodes, one per enabled Availability Zone; AWS removes a zone's address from DNS when that zone has no healthy target.
  - [AWS: Health checks for Network Load Balancer target groups](https://docs.aws.amazon.com/elasticloadbalancing/latest/network/target-group-health-checks.html) (primary)
  - [AWS: What is a Network Load Balancer?](https://docs.aws.amazon.com/elasticloadbalancing/latest/network/introduction.html) (primary)

- **c2** A Network Load Balancer monitors the health of its registered targets and routes traffic only to healthy targets.
  - [AWS: What is a Network Load Balancer?](https://docs.aws.amazon.com/elasticloadbalancing/latest/network/introduction.html) (primary)
  - [AWS: Health checks for Network Load Balancer target groups](https://docs.aws.amazon.com/elasticloadbalancing/latest/network/target-group-health-checks.html) (primary)

- **c3** By default each load balancer node distributes traffic across the registered targets in its own Availability Zone.
  - [AWS: What is a Network Load Balancer?](https://docs.aws.amazon.com/elasticloadbalancing/latest/network/introduction.html) (primary)

- **c4** An Ingress rule matches HTTP requests on host and path and sends them to the listed backend, which is a Service name and port.
  - [Kubernetes documentation: Ingress](https://kubernetes.io/docs/concepts/services-networking/ingress/) (primary)
  - [NGINX Ingress Controller documentation: Basic configuration](https://docs.nginx.com/nginx-ingress-controller/configuration/ingress-resources/basic-configuration) (primary)

- **c5** An Ingress does nothing by itself; an ingress controller such as NGINX fulfils the rules.
  - [Kubernetes documentation: Ingress](https://kubernetes.io/docs/concepts/services-networking/ingress/) (primary)

- **c6** A Service is an abstraction that gives a set of pods one stable name and virtual IP address; the virtual IP is implemented by rules that kube-proxy programs on each node, not by a process listening on that address.
  - [Kubernetes documentation: Service](https://kubernetes.io/docs/concepts/services-networking/service/) (primary)
  - [Kubernetes documentation: Virtual IPs and Service Proxies](https://kubernetes.io/docs/reference/networking/virtual-ips/) (primary)
  - [How does traffic actually reach your Pods? (dev.to)](https://dev.to/sreekanth_kuruba_91721e5d/how-does-traffic-actually-reach-your-pods-kubernetes-services-kube-proxy-explained-ph9) (secondary)

- **c7** NGINX Ingress Controller enumerates the pods of the backend Service and balances traffic directly to them unless told to use the Service's cluster IP.
  - [NGINX Ingress Controller documentation: NGINX Ingress Controller and Istio Service Mesh](https://docs.nginx.com/nginx-ingress-controller/tutorials/nginx-ingress-istio) (primary)

- **c8** Each pod has its own IP address.
  - [Kubernetes documentation: Service](https://kubernetes.io/docs/concepts/services-networking/service/) (primary)
