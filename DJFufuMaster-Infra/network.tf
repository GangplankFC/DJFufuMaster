resource "oci_core_vcn" "dj_fufu_master_vcn" {
  compartment_id = var.compartment_ocid
  cidr_blocks    = ["10.0.0.0/16"]
  display_name   = "dj-fufu-master-vcn"
  dns_label      = "djfufuvcn"
}

# 2. Create an Internet Gateway
resource "oci_core_internet_gateway" "dj_fufu_master_igw" {
  compartment_id = var.compartment_ocid
  vcn_id         = oci_core_vcn.dj_fufu_master_vcn.id
  display_name   = "dj-fufu-master-igw"
}

# 3. Route Traffic to the Internet
resource "oci_core_default_route_table" "dj_fufu_master_default_rt" {
  manage_default_resource_id = oci_core_vcn.dj_fufu_master_vcn.default_route_table_id

  route_rules {
    network_entity_id = oci_core_internet_gateway.dj_fufu_master_igw.id
    destination       = "0.0.0.0/0"
  }
}

# 4. Create a Subnet inside the VCN
resource "oci_core_subnet" "dj_fufu_master_subnet" {
  compartment_id    = var.compartment_ocid
  vcn_id            = oci_core_vcn.dj_fufu_master_vcn.id
  cidr_block        = "10.0.1.0/24"
  display_name      = "dj-fufu-master-subnet"
  dns_label         = "djfufusubnet"
  route_table_id    = oci_core_vcn.dj_fufu_master_vcn.default_route_table_id
  security_list_ids = [oci_core_vcn.dj_fufu_master_vcn.default_security_list_id]
}