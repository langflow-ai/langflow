output "manager_public_ips" {
  value = module.docker-swarm.manager_public_ips
}

output "worker_public_ips" {
  value = module.docker-swarm.worker_public_ips
}

